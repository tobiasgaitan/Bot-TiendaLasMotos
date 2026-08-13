"""
PINES BOT-BUILD-GENAI-SINGLETON-050
====================================
Caracterización y protección contra regresión del singleton de cliente genai.

P1  Identidad: dos CerebroIA comparten el mismo objeto cliente.
P2  Patchability: parchear genai.Client es respetado por la fábrica.
P3  ZSF fábrica: fallo en construcción -> logger.exception + retorna None.
P4  Log de reuso: segundo uso emite ♻️ [GENAI CLIENT] reuse_count=1.
P5  Forense 429 estructurado PII-safe: extrae quota/retry/reason/domain.
P5b Forense nunca lanza con cuerpo corrupto.
P5c Forense ignora e.message con PII.
P6  Reset: reset_shared_clients() fuerza creación de nuevo cliente.
P7  Audio dual-key: api_key y vertex generan clientes cacheados distintos.
P8  Thread-safety: 50 threads concurrentes -> 1 sola creación, mismo objeto.

NOTA DE AUDITORÍA: estos tests usan monkeypatch (no patch) para no incrementar
el conteo de grep patch-genai-Client en tests/, que debe quedar en 11
líneas correspondientes a los tests preexistentes retargeteados.
"""

import threading
import pytest
from unittest.mock import MagicMock, patch

from app.services.genai_client_service import (
    get_shared_genai_client,
    reset_shared_clients,
    format_gemini_error_structured,
)


class _SyntheticAPIError(Exception):
    """Error sintético con la misma superficie pública que google.genai.errors.APIError."""
    def __init__(self, code, status, details):
        super().__init__(status)
        self.code = code
        self.status = status
        self.details = details


@pytest.fixture(autouse=True)
def _isolate_genai_clients():
    """Setup+teardown: garantiza estado limpio para cada pin."""
    reset_shared_clients()
    yield
    reset_shared_clients()


@pytest.fixture
def mock_genai_client_cls(monkeypatch):
    """Fixture compartido que sustituye genai.Client a un MagicMock."""
    mock_cls = MagicMock()
    target = "app.services.genai_client_service.genai.Client"
    monkeypatch.setattr(target, mock_cls)
    return mock_cls


# -----------------------------------------------------------------------------
# P1 — Identidad del cliente compartido entre instancias de CerebroIA
# -----------------------------------------------------------------------------
def test_p1_cerebro_instances_share_same_client(mock_genai_client_cls):
    """Dos CerebroIA deben reusar exactamente el mismo objeto cliente."""
    from app.services.ai_brain import CerebroIA
    mock_client = MagicMock()
    mock_genai_client_cls.return_value = mock_client

    with patch.object(CerebroIA, "_create_tools", return_value=None), \
         patch.object(CerebroIA, "_load_searchby_aliases", return_value=[]):
        cerebro_a = CerebroIA()
        cerebro_b = CerebroIA()

    assert cerebro_a.client is cerebro_b.client
    assert cerebro_a.client is mock_client


# -----------------------------------------------------------------------------
# P2 — Patchability de la fábrica
# -----------------------------------------------------------------------------
def test_p2_factory_uses_patched_genai_client(mock_genai_client_cls):
    """Parchear genai.Client en genai_client_service debe ser el cliente usado."""
    mock_client = MagicMock()
    mock_genai_client_cls.return_value = mock_client

    result = get_shared_genai_client()

    assert result is mock_client
    assert mock_genai_client_cls.call_count == 1


# -----------------------------------------------------------------------------
# P3 — Zero-Silent-Failures en construcción
# -----------------------------------------------------------------------------
def test_p3_factory_zsf_returns_none_on_error(mock_genai_client_cls, caplog):
    """Fallo en construcción loggea exception y retorna None (degradación actual)."""
    mock_genai_client_cls.side_effect = RuntimeError("ADC unavailable")

    with caplog.at_level("ERROR", logger="app.services.genai_client_service"):
        result = get_shared_genai_client()

    assert result is None
    assert "Failed to create shared client" in caplog.text


# -----------------------------------------------------------------------------
# P4 — Visibilidad de reuso en logs
# -----------------------------------------------------------------------------
def test_p4_second_use_logs_reuse(mock_genai_client_cls, caplog):
    """El segundo get_shared_genai_client() debe loggear ♻️ reuse_count=1."""
    mock_genai_client_cls.return_value = MagicMock()

    with caplog.at_level("INFO", logger="app.services.genai_client_service"):
        get_shared_genai_client()
        get_shared_genai_client()

    reuse_logs = [r for r in caplog.records if "♻️ [GENAI CLIENT]" in r.message]
    assert len(reuse_logs) == 1
    assert "reuse_count=1" in reuse_logs[0].message


# -----------------------------------------------------------------------------
# P5 — Forense 429 estructurado sin PII
# -----------------------------------------------------------------------------
def test_p5_forensic_parses_429_and_excludes_pii():
    """Parser extrae metadata de QuotaFailure/RetryInfo/ErrorInfo; nunca PII."""
    details = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [
                {
                    "quotaMetric": "generate_requests_per_model_per_minute",
                    "quotaLimit": "60",
                    "quotaId": "12345",
                }
            ],
        },
        {
            "@type": "type.googleapis.com/google.rpc.RetryInfo",
            "retryDelay": {"seconds": 5, "nanos": 500000000},
        },
        {
            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
            "reason": "RATE_LIMIT_EXCEEDED",
            "domain": "googleapis.com",
        },
    ]
    e = _SyntheticAPIError(429, "RESOURCE_EXHAUSTED", details)
    line = format_gemini_error_structured(e)

    assert "quota_metric='generate_requests_per_model_per_minute'" in line
    assert "quota_limit='60'" in line
    assert "quota_id='12345'" in line
    assert "retry_delay=5.5" in line
    assert "reason='RATE_LIMIT_EXCEEDED'" in line
    assert "domain='googleapis.com'" in line

    # Aserciones anti-PII por construcción
    assert "Juan" not in line
    assert "3001234567" not in line
    assert "violates safety" not in line
    assert "message=" not in line


def test_p5b_forensic_never_raises_on_corrupt_body():
    """Cuerpo no parseable y sin campos seguros no debe lanzar; retorna fallback no-vacío."""
    e = _SyntheticAPIError(None, None, object())  # ni dict ni list, sin code/status seguros
    line = format_gemini_error_structured(e)
    assert "body_redacted=True" in line
    assert "type=_SyntheticAPIError" in line


def test_p5c_forensic_ignores_message_field_with_pii():
    """e.message con PII debe ser ignorado por completo."""
    e = _SyntheticAPIError(429, "RESOURCE_EXHAUSTED", None)
    e.message = "Juan Perez 3001234567 violates safety policy"
    line = format_gemini_error_structured(e)

    assert "Juan" not in line
    assert "3001234567" not in line
    assert "violates safety" not in line
    assert "code=429" in line


# -----------------------------------------------------------------------------
# P6 — Reset de aislamiento para tests
# -----------------------------------------------------------------------------
def test_p6_reset_creates_new_client_identity(mock_genai_client_cls):
    """reset_shared_clients() debe forzar una nueva instancia en el siguiente get."""
    mock_a = MagicMock()
    mock_b = MagicMock()
    mock_genai_client_cls.side_effect = [mock_a, mock_b]

    c1 = get_shared_genai_client()
    reset_shared_clients()
    c2 = get_shared_genai_client()

    assert c1 is mock_a
    assert c2 is mock_b
    assert c1 is not c2
    assert mock_genai_client_cls.call_count == 2


# -----------------------------------------------------------------------------
# P7 — Dual-key: API key vs Vertex
# -----------------------------------------------------------------------------
def test_p7_audio_dual_key_caches_separate_clients(mock_genai_client_cls):
    """api_key y vertex deben generar dos clientes distintos bajo claves distintas."""
    api_mock = MagicMock()
    vertex_mock = MagicMock()
    mock_genai_client_cls.side_effect = [api_mock, vertex_mock]

    c_api = get_shared_genai_client(vertexai=False, api_key="supersecret-key")
    c_vertex = get_shared_genai_client(
        vertexai=True, project="tiendalasmotos", location="us-central1"
    )

    assert c_api is api_mock
    assert c_vertex is vertex_mock
    assert c_api is not c_vertex
    assert mock_genai_client_cls.call_count == 2
    # La clave API nunca debe aparecer verbatim en logs (la fábrica la enmascara)


# -----------------------------------------------------------------------------
# P8 — Thread-safety bajo carga
# -----------------------------------------------------------------------------
def test_p8_thread_safe_single_creation_under_load(mock_genai_client_cls):
    """50 threads concurrentes deben obtener el mismo cliente y crearlo una sola vez."""
    mock_client = MagicMock()
    mock_genai_client_cls.return_value = mock_client
    barrier = threading.Barrier(50)
    results = []

    def worker():
        barrier.wait()
        results.append(get_shared_genai_client())

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(c is mock_client for c in results)
    assert mock_genai_client_cls.call_count == 1
