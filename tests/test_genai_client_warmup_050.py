"""
P10 BOT-BUILD-GENAI-SINGLETON-050-R2
=====================================
Caracterización del path anti-zombi del warm-up de GenAI en app/main.py.

P10a: timeout de 30s + completación natural EXITOSA -> genai_client_ready=True,
      catalog_ready=True, sin estado zombi.
P10b: timeout de 30s + completación natural con fallo (None) -> fail-closed real:
      genai_client_ready=False, catalog_ready=False, genai_client_failed=True.

REAL-LIFESPAN-EXEMPTION (04-03b): este archivo ejercita el lifespan real de
producción con proxies mockeados, siguiendo el patrón de tests/test_startup_lock.py.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.main import app, lifespan
from app.services.catalog_service import catalog_service
from tests.factories import make_catalog


class _TimeoutOn30sWaitFor:
    """
    Simula asyncio.wait_for levantando TimeoutError SOLO cuando se llama con
    el timeout real de warm-up de GenAI (app.main._GENAI_WARMUP_TIMEOUT_S);
    en cualquier otro caso pasa el await (natural completion). Usado por P10
    para no dormir 30s reales y mantenerse sincronizado con el código.
    """

    async def __call__(self, aw, timeout):
        import app.main

        if timeout == app.main._GENAI_WARMUP_TIMEOUT_S:
            raise asyncio.TimeoutError
        return await aw


@pytest.mark.asyncio
async def test_p10a_genai_warmup_timeout_then_success_no_zombie(caplog):
    """
    [BOT-BUILD-GENAI-SINGLETON-050-R2 / P10a]
    El warm-up genai excede 30s pero completa naturalmente. El patrón anti-zombi
    debe hacer commit de genai_client_ready=True y catalog_ready=True.
    """
    mock_client = MagicMock()

    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service, \
         patch("app.main.init_memory_service") as mock_init_memory, \
         patch.object(catalog_service, "get_all_items", return_value=make_catalog(60)), \
         patch("app.main.get_shared_genai_client", return_value=mock_client), \
         patch("app.main.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.main.asyncio.wait_for", new=_TimeoutOn30sWaitFor()):

        mock_settings.db_timeout = 5
        mock_settings.gcp_project_id = "test-project"
        mock_settings.min_catalog_items = 60
        mock_creds.return_value = MagicMock()

        async with lifespan(app):
            await app.state.startup_task

        assert app.state.genai_client_ready is True
        assert app.state.catalog_ready is True
        assert getattr(app.state, "genai_client_failed", False) is False
        assert any(
            "[DEFERRED-INIT-TIMEOUT] GenAI warm-up exceeded" in r.message
            for r in caplog.records
        ), "El path anti-zombi (timeout + log warning) no se ejercitó"


@pytest.mark.asyncio
async def test_p10b_genai_warmup_timeout_then_failure_fail_closed(caplog):
    """
    [BOT-BUILD-GENAI-SINGLETON-050-R2 / P10b]
    El warm-up genai excede 30s y la completación natural retorna None.
    Fail-closed real: genai_client_ready=False, catalog_ready=False,
    genai_client_failed=True.
    """
    with patch("app.main.settings") as mock_settings, \
         patch("app.main.get_firebase_credentials_object") as mock_creds, \
         patch("app.main.firestore") as mock_firestore, \
         patch("app.main.ConfigLoader") as mock_config_loader, \
         patch("app.main.config_service") as mock_config_service, \
         patch("app.main.FinanceConfigLoader") as mock_finance_config_loader, \
         patch("app.main.storage_service") as mock_storage_service, \
         patch("app.main.init_memory_service") as mock_init_memory, \
         patch.object(catalog_service, "get_all_items", return_value=make_catalog(60)), \
         patch("app.main.get_shared_genai_client", return_value=None), \
         patch("app.main.asyncio.sleep", new_callable=AsyncMock), \
         patch("app.main.asyncio.wait_for", new=_TimeoutOn30sWaitFor()):

        mock_settings.db_timeout = 5
        mock_settings.gcp_project_id = "test-project"
        mock_settings.min_catalog_items = 60
        mock_creds.return_value = MagicMock()

        async with lifespan(app):
            await app.state.startup_task

        assert app.state.genai_client_ready is False
        assert app.state.catalog_ready is False
        assert app.state.genai_client_failed is True
        assert any(
            "[DEFERRED-INIT-TIMEOUT] GenAI warm-up exceeded" in r.message
            for r in caplog.records
        ), "El path anti-zombi (timeout + log warning) no se ejercitó"
