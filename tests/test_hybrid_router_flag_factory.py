"""Certificación de flag, fail-closed e inmutabilidad C4 — BOT-BUILD-HYBRID-SYNTH-094.

COND-1: socket guard autouse.
COND-2: registro NB C5-129 (caché de facades) documentado.
"""
from __future__ import annotations

import hashlib
import os
import socket
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from app.services.hybrid_llm_router import HybridLLMRouter
from app.services.llm_client_service import (
    DualProviderClient,
    _invalidate_hybrid_flag_cache,
    get_shared_llm_client,
    get_shared_llm_client_async,
    reset_shared_llm_clients,
)


# ---------------------------------------------------------------------------
# COND-1: socket guard autouse
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _block_sockets():
    """Bloquea cualquier intento de socket real durante los tests."""
    original = socket.socket

    def _guard(*args, **kwargs):
        # COND-1: bloquear solo sockets de red reales; AF_UNIX lo usa asyncio.
        if args and args[0] in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("SOCKET_BLOCKED: la suite sintética no debe usar red")
        return original(*args, **kwargs)

    socket.socket = _guard
    yield
    socket.socket = original


# ---------------------------------------------------------------------------
# Hashes C4 (SHA-256) de los archivos SSOT protegidos. Actualizar solo bajo
# orden literal futura que modifique C4.
# ---------------------------------------------------------------------------
_C4_PINNED_HASHES: dict[str, str] = {
    "app/services/ai_brain.py": "e93a87b82949c7af3d2077a6a447dae30936f280aa2bc91d59d2f81ce0f3c9e3",
    "app/core/prompts.py": "4df9d72898dbe9c11e4425674233cd84d789bc0e113cf7fb87920f415416505e",
    "app/core/personality.json": "c10df9d243498528437a101f0705244388d9e416268017787db94c317df539e3",
}


class TestC4Immutability:
    def test_pinned_ssot_files_are_byte_identical(self) -> None:
        """Pin C4: los espejos SSOT no cambian sin acto consciente documentado."""
        for rel_path, expected_sha in _C4_PINNED_HASHES.items():
            path = Path(rel_path)
            assert path.exists(), f"Archivo C4 faltante: {rel_path}"
            actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual_sha == expected_sha, (
                f"C4_PIN_FAIL {rel_path}: hash {actual_sha} != {expected_sha}. "
                "Si el cambio fue autorizado, actualiza el pin bajo orden literal."
            )

    def test_nonexistent_c4_paths_are_still_absent(self) -> None:
        """El ticket hereda referencias a rutas que no existen en el working tree.

        Se protege su ausencia para detectar cualquier intento de introducir
        esos archivos sin gobernanza.
        """
        assert not Path("app/core/ai_brain.py").exists()
        assert not Path("app/core/juan_pablo_personality.docx").exists()


# ---------------------------------------------------------------------------
# Helpers de fábrica
# ---------------------------------------------------------------------------
def _mock_gemini_backend():
    """Patch de los constructores de clientes Gemini para evitar credenciales reales."""
    return patch(
        "app.services.llm_client_service.get_shared_genai_client",
        return_value=Mock(name="gemini_sync"),
    ), patch(
        "app.services.llm_client_service.get_shared_genai_client_async",
        return_value=Mock(name="gemini_async"),
    )


def _patch_hybrid_flag(value: bool):
    return patch(
        "app.services.llm_client_service._read_hybrid_flag_from_firestore",
        return_value=value,
    )


# ---------------------------------------------------------------------------
# G — Flag y fail-closed
# ---------------------------------------------------------------------------
class TestFlagAndFailClosed:
    """NB C5-129: el facade se cachea por key en _SHARED_LLM_CLIENTS.

    El flip del flag solo afecta a nuevas construcciones de facade. En
    producción, el efecto operacional es post-TTL o post-redeploy de instancias
    Cloud Run. Los tests invalidan explícitamente el cache para simular el
    rollback caliente.
    """

    def test_secret_missing_falls_back_to_gemini(self) -> None:
        """G1: OPENROUTER_API_KEY ausente → DualProviderClient + log HYBRID BOOTSTRAP."""
        env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
        sync_patch, async_patch = _mock_gemini_backend()
        with patch.dict(os.environ, env, clear=True):
            with sync_patch, async_patch, _patch_hybrid_flag(True):
                client = get_shared_llm_client(role="agentic")

        assert isinstance(client, DualProviderClient)
        assert not isinstance(client, HybridLLMRouter)

    def test_flag_false_returns_legacy_dual_provider(self) -> None:
        """G2: flag=false → facade legacy inerte (sin eventos HYBRID ROUTE)."""
        sync_patch, async_patch = _mock_gemini_backend()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_openrouter_key_094"}):
            with sync_patch, async_patch, _patch_hybrid_flag(False):
                client = get_shared_llm_client(role="agentic")

        assert isinstance(client, DualProviderClient)
        assert not isinstance(client, HybridLLMRouter)

    def test_hot_rollback_true_to_false(self) -> None:
        """G3: invalidar caché + flag false retorna a legacy."""
        sync_patch, async_patch = _mock_gemini_backend()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_openrouter_key_094"}):
            with sync_patch, async_patch, _patch_hybrid_flag(True):
                client_a = get_shared_llm_client(role="agentic")
        assert isinstance(client_a, HybridLLMRouter)

        # Simulación del rollback caliente: limpiar cache y flag.
        reset_shared_llm_clients()
        _invalidate_hybrid_flag_cache()

        sync_patch2, async_patch2 = _mock_gemini_backend()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_openrouter_key_094"}):
            with sync_patch2, async_patch2, _patch_hybrid_flag(False):
                client_b = get_shared_llm_client(role="agentic")
        assert isinstance(client_b, DualProviderClient)
        assert not isinstance(client_b, HybridLLMRouter)

    @pytest.mark.asyncio
    async def test_async_factory_flag_true_returns_hybrid(self) -> None:
        """La fábrica async respeta el flag híbrido."""
        sync_patch, async_patch = _mock_gemini_backend()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_openrouter_key_094"}):
            with sync_patch, async_patch, _patch_hybrid_flag(True):
                client = await get_shared_llm_client_async(role="agentic")
        assert isinstance(client, HybridLLMRouter)
