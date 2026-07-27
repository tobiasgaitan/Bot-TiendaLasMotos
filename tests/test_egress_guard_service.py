"""
Tests del Egress Guard — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001] (Fase 1).

Cobertura certificada por el ticket #M3-ETAPA6-001:
- URL-Lock: whitelist default-deny (dominios canónicos vs. auteco.com.co y
  externos), sustitución automática contra el SSOT del catálogo (match exacto
  normalizado, stem de archivo único, contención de tokens única), extirpación
  sin candidato único, y sustitución de URL de privacidad.
- Coerción de longitud: 4 líneas / 350 caracteres (truncado por \n primero,
  por caracteres después) con preservación de la pregunta de cierre.
- Integración en los 3 puntos de egreso del router (firma pública preservada).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import egress_guard_service as guard


# ---------------------------------------------------------------------------
# Fixtures de catálogo (SSOT simulado: pagina/catalogo/items → imagen_url)
# ---------------------------------------------------------------------------

CANONICAL_URL = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/"
    "motos%2Ftvs-sport-100.webp?alt=media&token=abc123"
)
CANONICAL_URL_2 = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/"
    "motos%2Ftvs-raider-125.webp?alt=media&token=def456"
)


@pytest.fixture
def catalog_ssot(monkeypatch):
    """Inyecta un catálogo mínimo en el singleton (índice O(1) + items)."""
    from app.services.catalog_service import CatalogService, catalog_service

    items = [
        {"id": "tvs_sport_100", "name": "TVS Sport 100", "image_url": CANONICAL_URL},
        {"id": "tvs_raider_125", "name": "TVS Raider 125", "image_url": CANONICAL_URL_2},
    ]
    index = {CatalogService._normalize_image_url(i["image_url"]): i for i in items}
    monkeypatch.setattr(catalog_service, "_items", items, raising=False)
    monkeypatch.setattr(catalog_service, "_items_by_image_url_norm", index, raising=False)
    return items


@pytest.fixture
def empty_catalog(monkeypatch):
    from app.services.catalog_service import catalog_service
    monkeypatch.setattr(catalog_service, "_items", [], raising=False)
    monkeypatch.setattr(catalog_service, "_items_by_image_url_norm", {}, raising=False)
    return catalog_service


# ---------------------------------------------------------------------------
# URL-Lock — whitelist default-deny
# ---------------------------------------------------------------------------

class TestUrlLockWhitelist:
    def test_canonical_image_host_passes_verbatim(self):
        text = f"Mira esta moto:\n![TVS Sport 100]({CANONICAL_URL})\n$5.999.000 ¿Te gusta?"
        out, report = guard.enforce_urls(text)
        assert CANONICAL_URL in out
        assert report.passed >= 1 and not report.stripped

    def test_canonical_text_hosts_pass(self):
        text = (
            "Política: https://tiendalasmotos.com/politica-de-privacidad y "
            "banco: https://slm.bancodebogota.com/mctn45s5"
        )
        out, report = guard.enforce_urls(text)
        assert "https://tiendalasmotos.com/politica-de-privacidad" in out
        assert "https://slm.bancodebogota.com/mctn45s5" in out
        assert not report.stripped

    def test_auteco_domain_image_token_stripped(self, empty_catalog):
        text = "Foto: ![Moto](https://auteco.com.co/img/tvs100.png) ¿Te interesa?"
        out, report = guard.enforce_urls(text)
        assert "auteco.com.co" not in out
        assert "![" not in out
        assert "¿Te interesa?" in out
        assert report.stripped and report.stripped[0].startswith("https://auteco.com.co")

    def test_external_domains_rejected(self, empty_catalog):
        for bad in (
            "https://autecomobility.com/x.png",
            "https://www.mercadolibre.com.co/moto-123",
            "https://evil-phishing.net/track?u=1",
        ):
            out, report = guard.enforce_urls(f"![M]({bad})")
            assert bad not in out
            assert report.stripped, f"{bad} no fue extirpada"

    def test_bare_external_url_stripped_keeping_text(self, empty_catalog):
        text = "Compra aquí https://auteco.com.co/ofertas antes de que se agote. ¿Vamos?"
        out, _ = guard.enforce_urls(text)
        assert "auteco.com.co" not in out
        assert "Compra aquí" in out and "¿Vamos?" in out

    def test_legacy_image_format_processed(self, empty_catalog):
        out, report = guard.enforce_urls("[IMAGE: https://auteco.com.co/x.webp]")
        assert "auteco.com.co" not in out
        assert report.stripped

    def test_privacy_intent_url_substituted_to_canonical(self, empty_catalog):
        out, report = guard.enforce_urls("Lee https://auteco.com.co/politica-privacidad porfa")
        assert guard.CANONICAL_PRIVACY_URL in out
        assert "auteco.com.co" not in out
        assert report.substituted


# ---------------------------------------------------------------------------
# URL-Lock — sustitución automática contra el SSOT del catálogo
# ---------------------------------------------------------------------------

class TestUrlLockSubstitution:
    def test_canonical_host_variant_passes_without_strip(self, catalog_ssot):
        # Host canónico con query corrupto: la política de dominio lo deja pasar
        # (la membresía en el índice es ayuda de sustitución, no barrera de red).
        variant = CANONICAL_URL.replace("token=abc123", "token=ZZZ")
        out, report = guard.enforce_urls(f"![TVS]({variant})")
        assert not report.stripped

    def test_filename_stem_unique_match_substitutes(self, catalog_ssot):
        hallucinated = "https://auteco.com.co/catalogo/tvs-sport-100.webp"
        out, report = guard.enforce_urls(f"![TVS Sport 100]({hallucinated})")
        assert CANONICAL_URL in out
        assert "auteco.com.co" not in out
        assert report.substituted and report.substituted[0][1] == CANONICAL_URL

    def test_ambiguous_stem_strips_instead_of_guessing(self, monkeypatch):
        from app.services.catalog_service import catalog_service
        dup1 = {"id": "moto_a", "name": "Moto A", "image_url": "https://firebasestorage.googleapis.com/a/tvs-sport-100.webp"}
        dup2 = {"id": "moto_b", "name": "Moto B", "image_url": "https://firebasestorage.googleapis.com/b/tvs-sport-100.webp"}
        monkeypatch.setattr(catalog_service, "_items", [dup1, dup2], raising=False)
        monkeypatch.setattr(catalog_service, "_items_by_image_url_norm", {}, raising=False)
        out, report = guard.enforce_urls("![M](https://auteco.com.co/tvs-sport-100.webp)")
        # Stem ambiguo (2 candidatos) Y tokens ambiguos → extirpar, jamás adivinar.
        assert "auteco.com.co" not in out
        assert "firebasestorage" not in out
        assert report.stripped

    def test_token_containment_unique_match_substitutes(self, catalog_ssot):
        # Stem sin match exacto de archivo, pero sus tokens quedan cubiertos por
        # UN solo ítem del catálogo (id+name): sustitución única y determinista.
        hallucinated = "https://cdn.externa.com/tvs-raider.jpg"
        out, report = guard.enforce_urls(f"![Raider]({hallucinated})")
        assert CANONICAL_URL_2 in out
        assert report.substituted and report.substituted[0][1] == CANONICAL_URL_2


# ---------------------------------------------------------------------------
# Coerción de longitud — 4 líneas / 350 caracteres
# ---------------------------------------------------------------------------

class TestLengthCoercion:
    def test_short_message_unchanged(self):
        text = "La TVS Sport 100 está a $5.999.000. ¿Te gustaría verla?"
        assert guard.enforce_length(text) == text

    def test_line_truncation_to_four(self):
        text = "L1\nL2\nL3\nL4\nL5\nL6"
        out = guard.enforce_length(text)
        assert out == "L1\nL2\nL3\nL4"
        assert len(out.split("\n")) == 4

    def test_question_beyond_window_is_preserved(self):
        text = "Dato A\nDato B\nDato C\nDato D\nDato E\n¿Cuál es tu tipo de vivienda?"
        out = guard.enforce_length(text)
        assert "¿Cuál es tu tipo de vivienda?" in out
        assert len(out.split("\n")) == 4
        assert "Dato D" not in out  # se eliminaron líneas intermedias, no la pregunta

    def test_char_truncation_never_mid_word(self):
        body = "palabra " * 80  # 640 chars, sin pregunta
        out = guard.enforce_length(body.strip())
        assert len(out) <= 350
        assert not out.endswith("palab")

    def test_closing_question_survives_char_truncation(self):
        question = "¿Cuál es tu tipo de vivienda?"
        body = ("La TVS Sport 100 tiene un motor confiable y económico. "
                "Es ideal para el trabajo diario en la ciudad. "
                "El consumo de combustible es excelente. ") * 3
        text = body.strip() + "\n" + question
        out = guard.enforce_length(text)
        assert len(out) <= 350
        assert out.endswith(question)
        assert question in out

    def test_question_alone_within_budget(self):
        out = guard.enforce_length("¿Con quién tengo el gusto?")
        assert out == "¿Con quién tengo el gusto?"

    def test_newline_collapse_before_counting(self):
        text = "L1\n\n\n\nL2"
        out = guard.enforce_length(text)
        assert "\n\n\n" not in out

    def test_paso4_legal_script_fits(self):
        # El script legal del PASO 4 (prompt SSOT) debe pasar intacto.
        script = (
            "Para hacer el estudio formal y validar tu cupo exacto con nuestro sistema, "
            "¿me autorizas el tratamiento de tus datos? (Política: "
            "https://tiendalasmotos.com/politica-de-privacidad). "
            "Solo confírmame con un 'Sí' o con un emoji de pulgar arriba (👍)."
        )
        assert guard.enforce_length(script) == script

    def test_protected_cuota_script_exempt(self):
        # Invariante 2: el script canónico cuota+Habeas (PASO 3/4, ai_brain)
        # excede 350 chars pero es contenido legal obligatorio → EXENTO.
        script = (
            "Si te interesa a crédito con la inicial de $650,000, "
            "las cuotas a 24 meses serían aproximadamente de $356,934 "
            "(incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*"
            "\n\nPara hacer el estudio formal de tu crédito y darte las opciones de financiación, "
            "¿me autorizas el tratamiento de tus datos personales de acuerdo con nuestra política de privacidad? "
            "(Política: https://tiendalasmotos.com/politica-de-privacidad). Solo confírmame con un 'Sí' o con un emoji de pulgar arriba (👍)."
        )
        assert len(script) > 350
        assert guard.enforce_length(script) == script


# ---------------------------------------------------------------------------
# Integración en los 3 puntos de egreso del router
# ---------------------------------------------------------------------------

class TestEgressIntegration:
    @pytest.mark.asyncio
    async def test_pipeline_strips_hallucinated_image_and_sends_text(self, empty_catalog):
        from app.routers.whatsapp import _process_and_send_egress_message

        sender = MagicMock()
        sender.send_text_message = AsyncMock(return_value={"ok": True})
        sender.send_image_message = AsyncMock(return_value={"ok": True})

        mock_ms = MagicMock()
        mock_ms.save_message = AsyncMock()

        response = (
            "Mira: ![Moto](https://auteco.com.co/foto.webp) "
            "La TVS Sport 100 cuesta $5.999.000. ¿Te animas?"
        )
        with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.services.whatsapp_service.whatsapp_service", sender):
            await _process_and_send_egress_message(
                "+573001112233", response, phone_number_id="pnid"
            )
        sender.send_image_message.assert_not_called()
        assert sender.send_text_message.called
        sent_text = sender.send_text_message.call_args[0][1]
        assert "auteco.com.co" not in sent_text

    @pytest.mark.asyncio
    async def test_image_boundary_rejects_bad_url_and_degrades_to_text(self, empty_catalog):
        from app.routers.whatsapp import _send_whatsapp_image

        sender = MagicMock()
        sender.send_text_message = AsyncMock(return_value={"ok": True})
        sender.send_image_message = AsyncMock(return_value={"ok": True})

        ok = await _send_whatsapp_image(
            "+573001112233", "https://auteco.com.co/foto.webp",
            caption="La moto cuesta $5.999.000. ¿La apartamos?",
            phone_number_id="pnid", meta_sender=sender,
        )
        assert ok is True
        sender.send_image_message.assert_not_called()
        sender.send_text_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_boundary_substitutes_canonical(self, catalog_ssot):
        from app.routers.whatsapp import _send_whatsapp_image

        sender = MagicMock()
        sender.send_image_message = AsyncMock(return_value={"ok": True})

        ok = await _send_whatsapp_image(
            "+573001112233", "https://auteco.com.co/tvs-sport-100.webp",
            caption="TVS Sport 100", phone_number_id="pnid", meta_sender=sender,
        )
        assert ok is True
        args = sender.send_image_message.call_args[0]
        assert args[1] == CANONICAL_URL

    @pytest.mark.asyncio
    async def test_text_boundary_enforces_length(self):
        from app.routers.whatsapp import _send_whatsapp_message

        sender = MagicMock()
        sender.send_text_message = AsyncMock(return_value={"ok": True})

        long_text = "Este es un mensaje extremadamente largo. " * 20 + "¿Confirmas?"
        ok = await _send_whatsapp_message(
            "+573001112233", long_text, phone_number_id="pnid", meta_sender=sender
        )
        assert ok is True
        sent_text = sender.send_text_message.call_args[0][1]
        assert len(sent_text) <= 350
        assert "¿Confirmas?" in sent_text

    @pytest.mark.asyncio
    async def test_text_boundary_rejects_external_url(self, empty_catalog):
        from app.routers.whatsapp import _send_whatsapp_message

        sender = MagicMock()
        sender.send_text_message = AsyncMock(return_value={"ok": True})

        ok = await _send_whatsapp_message(
            "+573001112233", "Entra a https://auteco.com.co ya. ¿Listo?",
            phone_number_id="pnid", meta_sender=sender,
        )
        assert ok is True
        sent_text = sender.send_text_message.call_args[0][1]
        assert "auteco.com.co" not in sent_text
        assert "¿Listo?" in sent_text
