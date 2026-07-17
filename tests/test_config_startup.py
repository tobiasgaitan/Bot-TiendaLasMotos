"""
test_config_startup.py — Prueba de Arranque de Settings() [BOT-INFRA-RECOVERY-PARAM-197]

WHY: Cierra el punto ciego detectado en la autopsia forense del ticket 197.
El conftest.py original nunca verificaba que Settings()._validate_config()
lanzara RuntimeError con credenciales ausentes. Esta omisión generó falsos
positivos en CI/CD que ocultaron el fallo de arranque en Cloud Run.

Garantías:
1. RuntimeError explícito cuando las 4 credenciales críticas están ausentes.
2. Settings() arranca correctamente con el pool completo de credenciales.
3. El strip() de tokens con whitespace no genera falso-positivo de ausencia.
"""
import os
import pytest
from unittest.mock import patch


# Variables que _validate_config() exige bajo pena de RuntimeError
FULL_POOL = {
    "WHATSAPP_TOKEN": "test_token_completo_197",
    "PHONE_NUMBER_ID": "1036387702901476",
    "ADMIN_API_KEY": "test_admin_key_not_a_real_secret_197",
    "WEBHOOK_VERIFY_TOKEN": "test_verify_token_197",
    "WHATSAPP_APP_SECRET": "test_app_secret_no_real",
    "MIN_CATALOG_ITEMS": "0",
    "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake-key.json",
}


class TestConfigStartup:
    """Suite de arranque de Settings() — Anti-Falso-Positivo [BOT-INFRA-RECOVERY-PARAM-197]"""

    def test_settings_raises_runtime_error_when_whatsapp_token_absent(self):
        """
        [BOT-INFRA-PARAM-197-A] Verifica que Settings() lanza RuntimeError
        si WHATSAPP_TOKEN está ausente — escenario exacto de purga de Cloud Run.
        """
        pool_sin_token = {k: v for k, v in FULL_POOL.items() if k != "WHATSAPP_TOKEN"}
        # Limpiar la variable del entorno para simular purga de Cloud Run
        pool_sin_token["WHATSAPP_TOKEN"] = ""

        with patch.dict(os.environ, pool_sin_token, clear=False):
            # CRÍTICO: descargar el módulo para forzar re-instanciación de Settings()
            import sys
            mods_to_remove = [m for m in sys.modules if "app.core.config" in m]
            for m in mods_to_remove:
                del sys.modules[m]

            with pytest.raises(RuntimeError, match="WHATSAPP_TOKEN"):
                from app.core.config import Settings
                Settings()

    def test_settings_raises_runtime_error_when_phone_number_id_absent(self):
        """
        [BOT-INFRA-PARAM-197-B] Verifica que Settings() lanza RuntimeError
        si PHONE_NUMBER_ID está ausente.
        """
        pool_sin_phone = {k: v for k, v in FULL_POOL.items()}
        pool_sin_phone["PHONE_NUMBER_ID"] = ""

        with patch.dict(os.environ, pool_sin_phone, clear=False):
            import sys
            mods_to_remove = [m for m in sys.modules if "app.core.config" in m]
            for m in mods_to_remove:
                del sys.modules[m]

            with pytest.raises(RuntimeError, match="PHONE_NUMBER_ID"):
                from app.core.config import Settings
                Settings()

    def test_settings_boots_successfully_with_full_pool(self):
        """
        [BOT-INFRA-PARAM-197-C] Verifica que Settings() arranca correctamente
        con el pool completo de credenciales — escenario del workflow CI/CD post-fix.
        """
        with patch.dict(os.environ, FULL_POOL, clear=False):
            import sys
            mods_to_remove = [m for m in sys.modules if "app.core.config" in m]
            for m in mods_to_remove:
                del sys.modules[m]

            from app.core.config import Settings
            s = Settings()

            assert s.whatsapp_token == "test_token_completo_197"
            assert s.phone_number_id == "1036387702901476"
            assert s.admin_api_key == "test_admin_key_not_a_real_secret_197"
            assert s.webhook_verify_token == "test_verify_token_197"

    def test_settings_strip_whitespace_does_not_cause_false_absence(self):
        """
        [BOT-INFRA-PARAM-197-D] Verifica que tokens con espacios/newlines laterales
        pasan la validación después del .strip() aplicado en config.py.
        La ausencia de strip() fue causa raíz del fallo en revisiones 00011-00015.
        """
        pool_with_whitespace = {**FULL_POOL, "WHATSAPP_TOKEN": "  test_token_con_espacios_197  "}

        with patch.dict(os.environ, pool_with_whitespace, clear=False):
            import sys
            mods_to_remove = [m for m in sys.modules if "app.core.config" in m]
            for m in mods_to_remove:
                del sys.modules[m]

            from app.core.config import Settings
            s = Settings()
            # Después del strip() el token debe ser el valor limpio
            assert s.whatsapp_token == "test_token_con_espacios_197"

    def test_settings_raises_for_insecure_default_values(self):
        """
        [BOT-INFRA-PARAM-197-E] Verifica que tokens con valores inseguros por defecto
        (moto_master_2026, motos2026) son rechazados por _validate_config().
        """
        pool_insecure = {**FULL_POOL, "WHATSAPP_TOKEN": "moto_master_2026"}

        with patch.dict(os.environ, pool_insecure, clear=False):
            import sys
            mods_to_remove = [m for m in sys.modules if "app.core.config" in m]
            for m in mods_to_remove:
                del sys.modules[m]

            with pytest.raises(RuntimeError, match="WHATSAPP_TOKEN"):
                from app.core.config import Settings
                Settings()
