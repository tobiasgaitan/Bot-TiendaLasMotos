import pytest
import asyncio
import subprocess
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic_loop_service import AgenticOrchestrator
from app.services.ai_brain import CerebroIA

@pytest.mark.asyncio
async def test_agentic_orchestrator_sandbox_async():
    """
    Test that create_sandbox and destroy_sandbox are async and execute subprocesses without blocking.
    """
    orchestrator = AgenticOrchestrator(sandbox_path="./tmp/test_sandbox")
    
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"mocked stdout", b"mocked stderr")
    mock_proc.returncode = 0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        # Test create_sandbox
        res = await orchestrator.create_sandbox("test_branch")
        assert res is True
        mock_exec.assert_called_with(
            "git", "worktree", "add", "-b", "test_branch", "./tmp/test_sandbox", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Test destroy_sandbox
        with patch("os.path.exists", return_value=True):
            await orchestrator.destroy_sandbox("test_branch")
            # We expect at least git worktree remove and git branch -D to be called (2 calls)
            assert mock_exec.call_count >= 2

@pytest.mark.asyncio
async def test_agentic_orchestrator_checker():
    """
    Verify run_checker enforces price ($), image format, and 'Ficha Tecnica:' (when is_catalog_query=True).
    """
    orchestrator = AgenticOrchestrator()
    
    # Normal catalog response containing all elements
    bot_response_ok = "La TVS Sport 100 cuesta $6.200.000. ![TVS Sport 100](http://image.url). Ficha Tecnica: Excelente rendimiento."
    val_ok = orchestrator.run_checker(bot_response_ok, is_catalog_query=True)
    assert val_ok["success"] is True
    
    # Missing price
    bot_response_no_price = "La TVS Sport 100 es excelente. ![TVS Sport](http://image.url). Ficha Tecnica: Excelente."
    val_fail_price = orchestrator.run_checker(bot_response_no_price, is_catalog_query=True)
    assert val_fail_price["success"] is False
    assert val_fail_price["report"]["broken_guardrail"] == "PRICE_CONSISTENCY_CHECK"
    
    # Missing image
    bot_response_no_image = "La TVS Sport 100 cuesta $6.200.000. Ficha Tecnica: Excelente."
    val_fail_image = orchestrator.run_checker(bot_response_no_image, is_catalog_query=True)
    assert val_fail_image["success"] is False
    
    # Missing Ficha Tecnica on catalog query
    bot_response_no_ficha = "La TVS Sport 100 cuesta $6.200.000. ![TVS Sport](http://image.url)."
    val_fail_ficha = orchestrator.run_checker(bot_response_no_ficha, is_catalog_query=True)
    assert val_fail_ficha["success"] is False

@pytest.mark.asyncio
async def test_ai_brain_validation_retry():
    """
    Test that ai_brain validates output using AgenticOrchestrator, and on failure retries
    with forced_temperature=0.1 and forced_instruction.
    """
    cerebro = CerebroIA()
    
    # We will mock _generate_with_retry_async to return:
    # 1st attempt: invalid response (missing price/image)
    # 2nd attempt: valid response
    calls = []
    async def mock_generate(texto, context, prospect_data, history, skip_greeting, forced_instruction=None, forced_temperature=None):
        calls.append({
            "forced_instruction": forced_instruction,
            "forced_temperature": forced_temperature
        })
        if len(calls) == 1:
            return "La TVS Sport es una gran moto."
        else:
            return "La TVS Sport cuesta $6.200.000. ![TVS Sport](http://img) Ficha Tecnica: 100cc"

    prospect_data = {
        "exists": True,
        "nombre": "Tobias",
        "ciudad": "Santa Marta",
        "forma_pago": "credito",
        "habeas_data_accepted": True,
        "moto_interest": "TVS Sport"
    }

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        
        response = await cerebro.pensar_respuesta(
            texto="especificaciones de la TVS Sport",
            context="",
            prospect_data=prospect_data,
            history=[],
            skip_greeting=True
        )
        
        # Verify pensar_respuesta returned the valid response (2nd attempt output after cleaning)
        assert "cuesta $6.200.000" in response
        assert "Ficha Tecnica:" in response
        
        # Verify it retried
        assert len(calls) == 2
        # First call has no forced temp
        assert calls[0]["forced_temperature"] is None
        # Second call has forced temp 0.1
        assert calls[1]["forced_temperature"] == 0.1
        assert "ERROR: La respuesta generada anteriormente falló la validación" in calls[1]["forced_instruction"]
