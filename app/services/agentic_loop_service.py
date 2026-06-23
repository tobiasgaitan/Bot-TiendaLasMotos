import os
import re
import json
import subprocess
import logging
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

    def create_sandbox(self, branch_name: str) -> bool:
        try:
            cmd = f"git worktree add -b {branch_name} {self.sandbox_path} main"
            result = subprocess.run(cmd.split(), capture_output=True, text=True, check=True)
            logger.info(f"Worktree creado exitosamente: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.exception(f"Error forense al crear Git Worktree: {e.stderr.strip()}")
            raise e

    def run_checker(self, bot_response: str, is_catalog_query: bool = False) -> Dict[str, Any]:
        has_price = bool(re.search(r"\$\d+", bot_response))
        has_image = bool(re.search(r"!\[.*?\]\(.*?\)|\[IMAGE:.*?\]", bot_response))
        has_ficha = "Ficha Tecnica:" in bot_response if is_catalog_query else True

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

    def destroy_sandbox(self, branch_name: str) -> None:
        try:
            if os.path.exists(self.sandbox_path):
                subprocess.run(f"git worktree remove --force {self.sandbox_path}".split(), check=True)
                subprocess.run(f"git branch -D {branch_name}".split(), check=True)
                logger.info("Sandbox efímero destruido físicamente de forma limpia.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Fallo crítico en el proceso de limpieza forense: {e.stderr}")

if __name__ == "__main__":
    print("AgenticOrchestrator: CLI Ready")
