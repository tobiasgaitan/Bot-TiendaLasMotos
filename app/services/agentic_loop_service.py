import os
import re
import json
import subprocess
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("agentic_loop")

class AgenticOrchestrator:
    def __init__(self, sandbox_path: str = "./tmp/sandbox-106", max_attempts: int = 5):
        self.sandbox_path = sandbox_path
        self.max_attempts = max_attempts
        self.error_schema_keys = [
            "scenario_key", "input_stimulus", "expected_behavior", 
            "output_obtained", "broken_guardrail", "code_context"
        ]

    async def create_sandbox(self, branch_name: str) -> bool:
        try:
            # cmd split: git worktree add -b {branch_name} {self.sandbox_path} main
            proc = await asyncio.create_subprocess_exec(
                "git", "worktree", "add", "-b", branch_name, self.sandbox_path, "main",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    returncode=proc.returncode,
                    cmd=["git", "worktree", "add", "-b", branch_name, self.sandbox_path, "main"],
                    output=stdout.decode("utf-8", errors="ignore"),
                    stderr=stderr.decode("utf-8", errors="ignore")
                )
            logger.info(f"Worktree creado exitosamente: {stdout.decode('utf-8', errors='ignore').strip()}")
            return True
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="ignore").strip() if e.stderr else "")
            logger.exception(f"Error forense al crear Git Worktree: {err_msg}")
            raise e

    def run_checker(self, bot_response: str, is_catalog_query: bool = False) -> Dict[str, Any]:
        has_price = bool(re.search(r"\$\d+", bot_response))
        has_image = bool(re.search(r"!\[.*?\]\(.*?\)|\[IMAGE:.*?\]", bot_response))
        has_ficha = bool(re.search(r"\s*Ficha Tecnica:", bot_response)) if is_catalog_query else True


        if not (has_price and has_image and has_ficha):
            report = {
                "scenario_key": "CATALOG_VALIDATION_FAIL",
                "input_stimulus": "Consulta de catálogo de motocicletas",
                "expected_behavior": "Respuesta con precio ($), imagen Markdown y prefijo Ficha Tecnica:",
                "output_obtained": bot_response if bot_response else "None / String Vacío",
                "broken_guardrail": "PRICE_CONSISTENCY_CHECK",
                "code_context": {
                    "target_file": "app/services/catalog_service.py",
                    "surrounding_code": "def search_items(): ...",
                    "logs_trace": "PCC Pro Validation Triggered: Assertion Error"
                }
            }
            return {"success": False, "report": report}
        
        return {"success": True, "report": {}}

    async def destroy_sandbox(self, branch_name: str) -> None:
        try:
            if os.path.exists(self.sandbox_path):
                proc1 = await asyncio.create_subprocess_exec(
                    "git", "worktree", "remove", "--force", self.sandbox_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout1, stderr1 = await proc1.communicate()
                if proc1.returncode != 0:
                    logger.error(f"Fallo al remover worktree: {stderr1.decode('utf-8', errors='ignore').strip()}")

                proc2 = await asyncio.create_subprocess_exec(
                    "git", "branch", "-D", branch_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout2, stderr2 = await proc2.communicate()
                if proc2.returncode != 0:
                    logger.error(f"Fallo al remover rama: {stderr2.decode('utf-8', errors='ignore').strip()}")

                logger.info("Sandbox efímero destruido físicamente de forma limpia.")
        except Exception as e:
            logger.error(f"Fallo crítico en el proceso de limpieza forense: {e}")

if __name__ == "__main__":
    print("AgenticOrchestrator: CLI Ready")

