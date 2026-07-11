import pytest
from app.routers import whatsapp

def test_langfuse_integration_integrity():
    """
    BOT-QA-GATE-110: Garantiza que el decorador importado no sea el fallback No-Op
    y que la observabilidad forense esté activa en el enrutador crítico.
    """
    # 1. Validar que no se esté usando el Shim de contingencia por fallo de importación
    assert whatsapp.observe.__name__ != "decorator", (
        "❌ REGRESIÓN DE OBSERVABILIDAD: Langfuse está desconectado. "
        "El enrutador cayó en el bloque de excepción y cargó el decorador ficticio (Shim)."
    )
    
    # 2. Validar que la función core mantenga el decorador de tracking de Langfuse
    assert hasattr(whatsapp._handle_message_background, "__wrapped__"), (
        "❌ VIOLACIÓN DE INTEGRIDAD: Se ha removido el decorador @observe "
        "de la función crítica _handle_message_background."
    )
