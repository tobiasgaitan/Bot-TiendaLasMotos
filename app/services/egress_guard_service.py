"""
Egress Guard Service — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001]
=============================================================
Interceptor determinista de la capa de egreso (previo al despacho a Meta).

Dos responsabilidades certificadas por el ticket #M3-ETAPA6-001:

1. URL-Lock Anti-Alucinación (§1 del diseño): política whitelist
   *default-deny*. Toda URL de imagen o de texto cuyo host no sea canónico
   se rechaza; se intenta sustitución automática contra el SSOT del catálogo
   (Firestore `pagina/catalogo/items` → `imagen_url`, índice O(1)
   `CatalogService._items_by_image_url_norm`) y, sin candidato único, se
   extirpa. NINGUNA URL alucinada cruza la frontera hacia Meta.
2. Coerción de longitud WhatsApp (§2 del diseño): cumplimiento estricto de
   <REGLAS_DE_LONGITUD_Y_CONCISION_WHATSAPP> — máximo 4 líneas (\\n) y 350
   caracteres — con preservación de la pregunta de cierre del embudo.

Sin I/O de red en la ruta caliente: la membresía canónica del catálogo es el
proxy determinista de "URL rota" (no se hacen HEAD requests).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL-Lock — política de dominios (whitelist default-deny)
# ---------------------------------------------------------------------------

#: Hosts canónicos para imágenes de catálogo (SSOT Firebase Storage + CDN propio).
ALLOWED_IMAGE_HOSTS = frozenset({
    "firebasestorage.googleapis.com",
    "tiendalasmotos.com",
})

#: Hosts canónicos para URLs de texto (privacidad + doctrina ruta 1 Banco de Bogotá).
ALLOWED_TEXT_HOSTS = frozenset({
    "tiendalasmotos.com",
    "slm.bancodebogota.com",
})

#: URL canónica de la política de privacidad (pin: app/core/config_loader.py L281).
CANONICAL_PRIVACY_URL = "https://tiendalasmotos.com/politica-de-privacidad"

_PRIVACY_INTENT_TOKENS = ("politica", "privacidad", "habeas")

# ---------------------------------------------------------------------------
# Coerción de longitud — regla de negocio <REGLAS_DE_LONGITUD_Y_CONCISION_WHATSAPP>
# ---------------------------------------------------------------------------

MAX_MESSAGE_LINES = 4
MAX_MESSAGE_CHARS = 350

#: Anclas canónicas protegidas (§2.2, invariante 2): scripts deterministas
#: generados por CÓDIGO (no verbosidad del LLM) cuyo contenido legal/financiero
#: es obligatorio y no cabe en 350 chars junto a la pregunta de Habeas Data.
#: Truncarlos destruiría cumplimiento (disclaimer de cuota). Un mensaje que
#: contiene un ancla protegida queda EXENTO de la coerción de caracteres.
PROTECTED_ANCHORS = (
    "*Nota: Este es un valor aproximado.*",  # Script PASO 3 cuota enganche (prompt SSOT + ai_brain)
)

# Markdown image/link token (paridad con el patrón del pipeline unificado de egreso,
# routers/whatsapp.py::_process_and_send_egress_message).
_MARKDOWN_IMG_RE = re.compile(r'(!?\[[\s\S]*?\]\s*\()\s*(https?://[^\s\)]+)\s*(\))')
_MARKDOWN_FULL_TOKEN_RE = re.compile(r'!?\[[\s\S]*?\]\s*\(https?://[^\s\)]+\)')
_LEGACY_IMG_RE = re.compile(r'\[IMAGE:\s*(https?://[^\s\]]+)\]')
_BARE_URL_RE = re.compile(r'https?://[^\s\)\]]+')

_QUESTION_RE = re.compile(r'¿[^¿?]*\?')


@dataclass
class UrlLockReport:
    """Reporte forense del URL-Lock (Zero-Silent-Failures, sin PII)."""
    extracted: int = 0
    passed: int = 0
    substituted: List[Tuple[str, str]] = field(default_factory=list)
    stripped: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"extraídas={self.extracted} pasadas={self.passed} "
            f"sustituidas={len(self.substituted)} extirpadas={len(self.stripped)}"
        )


def _host_of(url: str) -> str:
    try:
        return (urlparse(url.strip()).netloc or "").lower().split(":")[0]
    except Exception:
        return ""


def _is_privacy_intent(url: str) -> bool:
    low = url.lower()
    return any(tok in low for tok in _PRIVACY_INTENT_TOKENS)


def _filename_stem_key(url: str) -> str:
    """Stem del último segmento del path, normalizado con la llave canónica del catálogo."""
    try:
        from app.services.catalog_service import CatalogService
        segment = urlparse(url.strip()).path.rsplit("/", 1)[-1]
        stem = segment.rsplit(".", 1)[0] if "." in segment else segment
        return CatalogService._normalize_item_id_key(stem)
    except Exception:
        return ""


def _substitute_from_catalog(url: str, recommended_model: Optional[str] = None) -> Optional[str]:
    """
    Algoritmo de sustitución automática contra el SSOT del catálogo (§1.3):
      1. Match exacto O(1) por URL normalizada (índice _items_by_image_url_norm).
      2. Match por stem de archivo (único candidato).
      3. Contención de tokens del modelo (único candidato).
      4. Sin candidato único → None (el llamador extirpa; jamás se adivina).
    """
    try:
        from app.services.catalog_service import CatalogService, catalog_service
    except Exception as e:
        logger.warning(f"⚠️ [URL-LOCK] Catálogo no disponible para sustitución: {e}")
        return None

    try:
        index = getattr(catalog_service, "_items_by_image_url_norm", None) or {}
        items = getattr(catalog_service, "_items", None) or []
        if not items:
            return None

        # 1. Match exacto por URL normalizada
        norm = CatalogService._normalize_image_url(url)
        if norm and norm in index:
            canonical = (index[norm] or {}).get("image_url")
            if canonical:
                return canonical

        # 2. Match por stem de archivo (único)
        stem_key = _filename_stem_key(url)
        if stem_key:
            stem_cands = set()
            for item in items:
                if CatalogService._is_padded_item(item.get("id", "")):
                    continue
                item_url = item.get("image_url") or ""
                if item_url and _filename_stem_key(item_url) == stem_key:
                    stem_cands.add(item_url)
            if len(stem_cands) == 1:
                return stem_cands.pop()

        # 3. Contención de tokens del modelo (único)
        query_tokens = CatalogService._id_token_set(stem_key) if stem_key else frozenset()
        if len(query_tokens) >= 2:
            token_cands = set()
            for item in items:
                if CatalogService._is_padded_item(item.get("id", "")):
                    continue
                item_tokens = (
                    CatalogService._id_token_set(str(item.get("id", "")))
                    | CatalogService._id_token_set(str(item.get("name", "")))
                )
                item_url = item.get("image_url") or ""
                if item_url and item_tokens and query_tokens <= item_tokens:
                    token_cands.add(item_url)
            if len(token_cands) == 1:
                return token_cands.pop()

        # 4. Fallback al modelo canónico recomendado (BOT-BUILD-EGRESS-CANON-015)
        # Si la URL alucinada no pudo sustituirse por firma, resolvemos por el
        # modelo que el catálogo rankeó como TOP RESULT para la consulta original.
        if recommended_model:
            try:
                rec_clean = recommended_model.strip().lower()
                for item in items:
                    if str(item.get("name", "")).strip().lower() == rec_clean:
                        candidate_url = item.get("image_url") or ""
                        if candidate_url:
                            return candidate_url
                # Match exacto no encontrado: usar Top Result de search_items
                top_matches = catalog_service.search_items(recommended_model)
                if top_matches:
                    candidate_url = top_matches[0].get("image_url") or ""
                    if candidate_url:
                        return candidate_url
            except Exception as e:
                logger.exception(f"❌ [URL-LOCK] Error en fallback recommended_model '{recommended_model}': {e}")

        return None
    except Exception as e:
        # Zero-Silent-Failures: log forense; la extirpación sigue siendo el fallback seguro.
        logger.exception(f"❌ [URL-LOCK] Error en sustitución de catálogo para URL rechazada: {e}")
        return None


def image_owner_model(image_url: str) -> Optional[str]:
    """Devuelve el nombre del ítem de catálogo dueño de una image_url canónica."""
    try:
        from app.services.catalog_service import CatalogService, catalog_service
        if not image_url or not catalog_service:
            return None
        norm = CatalogService._normalize_image_url(image_url)
        if not norm:
            return None
        index = getattr(catalog_service, "_items_by_image_url_norm", None) or {}
        item = index.get(norm)
        if item:
            return item.get("name")
    except Exception:
        logger.exception("❌ [URL-LOCK] Error resolviendo dueño de imagen canónica")
    return None


def _classify_and_resolve_image_url(
    url: str,
    report: UrlLockReport,
    recommended_model: Optional[str] = None,
) -> Optional[str]:
    """Retorna la URL autorizada (original o sustituta) o None si debe extirparse."""
    host = _host_of(url)
    if host in ALLOWED_IMAGE_HOSTS:
        report.passed += 1
        return url
    substitute = _substitute_from_catalog(url, recommended_model=recommended_model)
    if substitute:
        report.substituted.append((url, substitute))
        logger.info(f"🔒 [URL-LOCK] URL no canónica sustituida por SSOT catálogo: host='{host}'")
        return substitute
    report.stripped.append(url)
    logger.warning(f"🚨 [URL-LOCK] URL de imagen NO canónica EXTIRPADA (default-deny): host='{host}'")
    return None


def _resolve_text_url(url: str, report: UrlLockReport) -> Optional[str]:
    """Política para URLs de texto desnudas. None = extirpar la URL del texto."""
    host = _host_of(url)
    if host in ALLOWED_TEXT_HOSTS or host in ALLOWED_IMAGE_HOSTS:
        report.passed += 1
        return url
    if _is_privacy_intent(url):
        report.substituted.append((url, CANONICAL_PRIVACY_URL))
        logger.info(f"🔒 [URL-LOCK] URL de privacidad no canónica sustituida: host='{host}'")
        return CANONICAL_PRIVACY_URL
    report.stripped.append(url)
    logger.warning(f"🚨 [URL-LOCK] URL de texto NO canónica EXTIRPADA (default-deny): host='{host}'")
    return None


def enforce_urls(
    text: str,
    recommended_model: Optional[str] = None,
) -> Tuple[str, UrlLockReport]:
    """
    URL-Lock (§1): valida cada URL extraída/generada por el LLM antes del despacho.
    Función pura (sin I/O de red). Retorna (texto_sanitizado, reporte).
    """
    report = UrlLockReport()
    if not text:
        return text, report

    # 1) Tokens Markdown de imagen/link: ![alt](url) — paridad con el pipeline unificado.
    def _markdown_sub(m: re.Match) -> str:
        report.extracted += 1
        open_part, url, close_part = m.group(1), m.group(2), m.group(3)
        resolved = _classify_and_resolve_image_url(url, report, recommended_model=recommended_model)
        if resolved is None:
            return ""  # extirpación del token completo
        return f"{open_part}{resolved}{close_part}"

    sanitized = _MARKDOWN_IMG_RE.sub(_markdown_sub, text)

    # 2) Formato legacy [IMAGE: url]
    def _legacy_sub(m: re.Match) -> str:
        report.extracted += 1
        resolved = _classify_and_resolve_image_url(m.group(1), report, recommended_model=recommended_model)
        return f"[IMAGE: {resolved}]" if resolved else ""

    sanitized = _LEGACY_IMG_RE.sub(_legacy_sub, sanitized)

    # 3) URLs desnudas remanentes (fuera de cualquier token ya procesado).
    def _bare_sub(m: re.Match) -> str:
        url = m.group(0)
        # Las URLs ya validadas dentro de tokens no se reprocesan: el token fue
        # reconstruido solo con URLs autorizadas; si el host es canónico pasa.
        report.extracted += 1
        resolved = _resolve_text_url(url, report)
        return resolved or ""

    sanitized = _BARE_URL_RE.sub(_bare_sub, sanitized)

    # Limpieza estructural post-extirpación (espacios/saltos huérfanos).
    sanitized = re.sub(r'[ \t]{2,}', ' ', sanitized)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)

    if report.substituted or report.stripped:
        logger.info(f"🔒 [URL-LOCK] {report.summary()}")
    return sanitized.strip(), report


def enforce_image_url(
    image_url: str,
    recommended_model: Optional[str] = None,
) -> Tuple[Optional[str], UrlLockReport]:
    """
    Variante para la frontera `_send_whatsapp_image` (defensa en profundidad, §1.1).
    Retorna (url_autorizada_o_None, reporte).
    """
    report = UrlLockReport(extracted=1 if image_url else 0)
    if not image_url:
        return None, report
    return _classify_and_resolve_image_url(image_url, report, recommended_model=recommended_model), report


# ---------------------------------------------------------------------------
# Coerción de longitud (§2) — 4 líneas / 350 chars con preservación de pregunta
# ---------------------------------------------------------------------------

def _truncate_body_to_budget(body: str, budget: int) -> str:
    """Trunca en límite de oración (preferido) o de palabra; jamás a media palabra."""
    body = body.rstrip()
    if len(body) <= budget:
        return body
    cut = body[:budget]
    # Límite de oración: último cierre '.', '!', '?' seguido de espacio o fin.
    sentence_end = -1
    for m in re.finditer(r'[.!?](?=\s|$)', cut):
        sentence_end = m.end()
    if sentence_end > budget * 0.4:
        return cut[:sentence_end].rstrip()
    last_space = cut.rfind(' ')
    if last_space > budget * 0.4:
        return cut[:last_space].rstrip() + '…'
    return cut.rstrip() + '…'


def _last_question_span(text: str) -> Optional[re.Match]:
    matches = list(_QUESTION_RE.finditer(text))
    return matches[-1] if matches else None


def enforce_length(
    text: str,
    max_lines: int = MAX_MESSAGE_LINES,
    max_chars: int = MAX_MESSAGE_CHARS,
) -> str:
    """
    Middleware coercitivo <REGLAS_DE_LONGITUD_Y_CONCISION_WHATSAPP> (§2.1):
    trunca PRIMERO por saltos de línea (máx. 4 segmentos \\n) y DESPUÉS por
    caracteres (máx. 350), preservando siempre la última pregunta interrogativa
    (invariante ONE-SHOT del embudo, §2.2).
    """
    if not text:
        return text

    # Invariante 2 (§2.2): los scripts canónicos deterministas (cuota enganche
    # PASO 3 + Habeas) son exentos — truncarlos destruiría contenido legal
    # obligatorio. La regla 4/350 gobierna la verbosidad del LLM, no el script legal.
    if any(anchor in text for anchor in PROTECTED_ANCHORS):
        return text

    original_chars = len(text)
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    # --- Fase 1: truncado por saltos de línea ---
    lines = text.split('\n')
    if len(lines) > max_lines:
        q_line_idx = max((i for i, ln in enumerate(lines) if '¿' in ln or '?' in ln), default=None)
        if q_line_idx is not None and q_line_idx >= max_lines:
            # La pregunta de cierre cae fuera de la ventana: se eliminan líneas
            # intermedias (nunca la pregunta) para que quepa en max_lines.
            lines = lines[:max_lines - 1] + [lines[q_line_idx]]
        else:
            lines = lines[:max_lines]
        text = '\n'.join(lines)

    # --- Fase 2: truncado por caracteres (con preservación de pregunta) ---
    if len(text) > max_chars:
        q_span = _last_question_span(text)
        if q_span is not None and len(q_span.group(0)) <= max_chars - 2:
            question = q_span.group(0)
            body = text[:q_span.start()].rstrip()
            sep = '\n' if '\n' in text[:q_span.start()] else ' '
            budget = max_chars - len(question) - len(sep)
            body_trunc = _truncate_body_to_budget(body, budget) if budget > 0 else ''
            text = f"{body_trunc}{sep}{question}" if body_trunc else question
        else:
            # Sin pregunta preservable (o pregunta degenerada > presupuesto):
            # truncado duro en límite de oración/palabra.
            if q_span is not None:
                logger.warning(
                    f"🚨 [EGRESS-LENGTH] Pregunta de cierre degenerada "
                    f"({len(q_span.group(0))} chars) excede el presupuesto; truncado duro."
                )
            text = _truncate_body_to_budget(text, max_chars)

    if len(text) != original_chars:
        logger.info(
            f"✂️ [EGRESS-LENGTH] Coerción aplicada: {original_chars}→{len(text)} chars "
            f"(máx {max_lines} líneas/{max_chars} chars)"
        )
    return text
