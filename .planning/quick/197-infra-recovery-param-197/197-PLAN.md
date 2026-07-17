---
task: 197
name: INFRA Recovery — Config Pool Consolidation
description: "Sincronizar el pool completo de secretos en deploy.yml, deploy-beta.yml y conftest.py para eliminar el RuntimeError de Settings() en Cloud Run"
ticket: BOT-INFRA-RECOVERY-PARAM-197
---

# Quick Task 197: INFRA Recovery — Config Pool Consolidation

## Objective
Eliminar el RuntimeError en app/core/config.py (linea 92/_log_config_status) causado por la purga silenciosa de variables de entorno en Cloud Run. Sincronizar el pool completo de secretos en los workflows CI/CD y cerrar el punto ciego del conftest que generaba falsos positivos.

## Autopsia del Falso Positivo
- conftest.py fixture mock_env_vars (autouse=True) solo inyecta GOOGLE_APPLICATION_CREDENTIALS, TEST_MODE, MIN_CATALOG_ITEMS
- NUNCA inyecta WHATSAPP_TOKEN, PHONE_NUMBER_ID, ADMIN_API_KEY, WEBHOOK_VERIFY_TOKEN
- Los tests pasan porque importan 'settings' ya cargado desde .env local con credenciales reales
- En Cloud Run con --set-env-vars manual, variables no declaradas se purgan => RuntimeError
- No existia ningun test que verificara Settings() con variables ausentes

## Tasks

<task type="auto">
  <name>Fix deploy.yml Pool Completo</name>
  <files>.github/workflows/deploy.yml</files>
  <action>Agregar WHATSAPP_APP_SECRET, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST al pool de --update-env-vars</action>
  <verify>grep -c "WHATSAPP_APP_SECRET" .github/workflows/deploy.yml</verify>
  <done>Todas las credenciales criticas en una sola instruccion atomica</done>
</task>

<task type="auto">
  <name>Fix deploy-beta.yml Pool Completo</name>
  <files>.github/workflows/deploy-beta.yml</files>
  <action>Sincronizar el mismo pool completo en deploy-beta.yml</action>
  <verify>grep -c "WHATSAPP_APP_SECRET" .github/workflows/deploy-beta.yml</verify>
  <done>Deploy beta contiene todas las variables criticas</done>
</task>

<task type="auto">
  <name>Fix conftest.py Cerrar Punto Ciego</name>
  <files>tests/conftest.py</files>
  <action>Agregar las 4 credenciales criticas al patch.dict de mock_env_vars</action>
  <verify>grep -c "WHATSAPP_TOKEN" tests/conftest.py</verify>
  <done>conftest.py incluye todas las credenciales criticas en el autouse fixture</done>
</task>

<task type="auto">
  <name>Crear test_config_startup.py</name>
  <files>tests/test_config_startup.py</files>
  <action>Crear test unitario que verifica RuntimeError con vars ausentes y arranque OK con pool completo</action>
  <verify>python3 -m pytest tests/test_config_startup.py -v 2>&1 | tail -10</verify>
  <done>2 tests pasan: ausencia lanza RuntimeError, presencia arranca OK</done>
</task>

---
*Created: 2026-07-17*
