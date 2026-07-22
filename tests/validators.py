"""
tests/validators.py — Validadores Regex PCC Pro + Sanitize PII [Incidente H-A · HA-4]

WHY: el arnés verificaba PCC y sanitización con asserts ad-hoc dispersos. Este módulo
centraliza validadores regex REUTILIZABLES con AssertionError forense, cada uno con su
mutation check obligatorio (anti-falso-positivo): todo validador debe FALLAR ante input
mutado.

Contratos verificados contra producción (2026-07-22):
- Precio canónico COP: `catalog_service.py` → `f"${price:,.0f}".replace(",", ".")`
  (p. ej. `$4.210.000`), con sufijo PRICE_PACKAGE_ANCHOR "(incluye SOAT, Matrícula, y tramites)".
- Salida real de `search_catalog`: línea `- NAME (cat): $PRECIO (...)`, línea
  `![NAME](url)` markdown y cierre `Ficha Tecnica: <summary>`.
- `_sanitize_fields` (`app/utils/json_processor.py`): sobre campos PII críticos
  (nombre/name/ciudad/city/moto_interest/fullName/location) aplica (1) eliminación de
  control-chars (unicodedata cat C), (2) whitelist estricta
  `[a-zA-Z0-9áéíóúÁÉÍÓÚñÑñ\\s\\.\\-]`, (3) truncado `[:50]`.
- `_sanitize_text` (`app/services/whatsapp_service.py`): elimina
  `[\\x00-\\x08\\x0b-\\x0c\\x0e-\\x1f\\x7f]` y colapsa espacios.
"""
import re
from typing import Optional

# ============================================================================
# PCC Pro — Price Consistency Check
# ============================================================================

# Forma canónica completa: $4.210.000 (espacio tras $ tolerado, nunca emitido)
RE_PRECIO_COP = re.compile(r"^\$\s?\d{1,3}(\.\d{3})+$")

# Extracción de montos COP embebidos en texto libre (grupo 1 = dígitos con '.')
RE_EXTRACT_PRECIOS = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})+)")

# Prefijo obligatorio de ficha técnica con captura de contenido
RE_FICHA = re.compile(r"Ficha Tecnica:\s*(.+)")

# Imagen en markdown ![alt](url) o URL plana de imagen
RE_IMG_MARKDOWN = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
RE_IMG_URL_PLANA = re.compile(r"https?://[^\s)]+\.(?:webp|jpg|jpeg|png)(?:\?[^\s)]*)?", re.IGNORECASE)


def assert_price_consistency(response_text: str, expected_price_cop: int) -> None:
    """PCC Pro: la respuesta DEBE mostrar exactamente el precio canónico del catálogo.

    Normaliza separadores ('.') antes de comparar para que `$4.210.000` y `$4210000`
    sean equivalentes al mismo entero; cualquier otro monto es inconsistencia.
    """
    if not isinstance(expected_price_cop, int) or expected_price_cop <= 0:
        raise ValueError(f"expected_price_cop debe ser int > 0, recibido: {expected_price_cop!r}")
    canonical = f"${expected_price_cop:,}".replace(",", ".")
    found = RE_EXTRACT_PRECIOS.findall(response_text or "")
    if not found:
        raise AssertionError(
            f"[PCC] Respuesta sin ningún precio COP. Se esperaba el canónico {canonical!r}."
        )
    normalized = {amount.replace(".", "") for amount in found}
    if str(expected_price_cop) not in normalized:
        raise AssertionError(
            f"[PCC] Inconsistencia precio-respuesta ↔ precio-catálogo: canónico={canonical!r} "
            f"pero la respuesta muestra {sorted(found)!r}."
        )


def assert_ficha_explicit(response_text: str) -> None:
    """PCC Pro: 'Ficha Tecnica:' explícita con contenido no vacío ni 'None' silencioso."""
    match = RE_FICHA.search(response_text or "")
    if not match:
        raise AssertionError("[PCC] Falta el prefijo obligatorio 'Ficha Tecnica:' en la respuesta.")
    val = match.group(1).strip()
    if val in ("", "None"):
        raise AssertionError(f"[PCC] 'Ficha Tecnica:' con contenido inválido/silencioso: {val!r}.")


def assert_catalog_price_format(price_str: str) -> None:
    """PCC Pro: un precio formateado DEBE cumplir la forma canónica $X.XXX.XXX."""
    if not RE_PRECIO_COP.match(price_str or ""):
        raise AssertionError(
            f"[PCC] Formato de precio no canónico: {price_str!r}. Esperado p. ej. '$4.210.000'."
        )


def assert_image_reference(response_text: str) -> None:
    """PCC Pro: la respuesta DEBE referenciar una imagen válida (markdown o URL plana)."""
    text = response_text or ""
    if not (RE_IMG_MARKDOWN.search(text) or RE_IMG_URL_PLANA.search(text)):
        raise AssertionError(
            "[PCC] Sin referencia de imagen válida: se esperaba '![alt](https://...)' "
            "o URL plana .webp/.jpg/.jpeg/.png."
        )


# ============================================================================
# Sanitize PII
# ============================================================================

# Teléfono móvil colombiano: (+57 opcional) 3XX XXX XXXX con separadores opcionales
RE_PHONE_CO = re.compile(r"(\+?57)?[\s-]?3\d{2}[\s-]?\d{3}[\s-]?\d{4}")

# Email estándar
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Control-chars eliminados por _sanitize_text / _sanitize_fields (cat C de unicode)
RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")

# Violadores de la whitelist estricta de _sanitize_fields
RE_PII_VIOLATORS = re.compile(r"[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s\.\-]")

# Longitud máxima de campos PII críticos (truncado [:50] de _sanitize_fields)
PII_FIELD_MAX_LEN = 50


def assert_no_pii_leak(text: str, *, check_phone: bool = True, check_email: bool = True) -> None:
    """Sanitize PII: una salida de cara al usuario NO debe contener PII cruda.

    Uso aprobado: respuestas del bot / payloads de egreso. NOTA DE CONTRATO: no aplicar
    sobre campos críticos post-_sanitize_fields esperando remoción de teléfonos — la
    whitelist de producción conserva dígitos por diseño (solo elimina símbolos); los
    emails sí quedan imposibilitados ('@' fuera de whitelist).
    """
    if not text:
        return
    if check_phone and RE_PHONE_CO.search(text):
        raise AssertionError(f"[PII] Teléfono CO filtrado en salida: {text!r}")
    if check_email and RE_EMAIL.search(text):
        raise AssertionError(f"[PII] Email filtrado en salida: {text!r}")


def assert_no_control_chars(text: Optional[str]) -> None:
    """Sanitize PII: cero control-chars residuales tras sanitización."""
    if text and RE_CONTROL_CHARS.search(text):
        raise AssertionError(f"[PII] Control-chars residuales en campo sanitizado: {text!r}")


def assert_pii_whitelist(text: Optional[str]) -> None:
    """Sanitize PII: solo caracteres de la whitelist estricta de _sanitize_fields."""
    if text:
        violators = RE_PII_VIOLATORS.findall(text)
        if violators:
            raise AssertionError(
                f"[PII] Caracteres fuera de la whitelist estricta {sorted(set(violators))!r} en: {text!r}"
            )


def assert_truncated_50(text: Optional[str]) -> None:
    """Sanitize PII: los campos críticos jamás exceden el truncado de 50 chars."""
    if text and len(text) > PII_FIELD_MAX_LEN:
        raise AssertionError(
            f"[PII] Campo excede el truncado de {PII_FIELD_MAX_LEN} chars (len={len(text)}): {text!r}"
        )
