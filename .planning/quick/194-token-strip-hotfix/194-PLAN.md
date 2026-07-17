---
task: 194
name: Token Strip Hotfix
description: Modificar 'app/core/config.py' en la carga de variables de entorno para aplicar un saneamiento agresivo (.strip()) sobre las credenciales críticas de la API (incluyendo 'WHATSAPP_TOKEN' y 'WHATSAPP_APP_SECRET') antes de ejecutar '_validate_config()'. Esto limpiará de forma automática cualquier espacio o salto de línea residual introducido por la terminal.
---

# Quick Task 194: Token Strip Hotfix

## Objective
Aplicar un saneamiento agresivo (.strip()) sobre las credenciales críticas de la API (incluyendo 'WHATSAPP_TOKEN' y 'WHATSAPP_APP_SECRET') al cargar variables de entorno en la clase Settings en `app/core/config.py` para evitar fallos de inicialización en Cloud Run causados por espacios en blanco o saltos de línea residuales.

## Tasks

<task type="auto">
  <name>Aplicar saneamiento agresivo a las credenciales críticas</name>
  <files>[app/core/config.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/core/config.py)</files>
  <action>Modificar la inicialización de la clase Settings en `app/core/config.py` para aplicar `.strip()` a `whatsapp_token`, `phone_number_id`, `webhook_verify_token`, `whatsapp_app_secret` y `admin_api_key` si están definidas, antes de llamar a `_validate_config()` o `_log_config_status()` o utilizarlas.</action>
  <verify>Ejecutar pytest en tests/test_startup_lock.py y verificar que los archivos de configuración no causen errores de sintaxis.</verify>
  <done>El código de config.py tiene aplicados los métodos .strip() y no genera errores de sintaxis.</done>
</task>

<task type="auto">
  <name>Agregar caso de prueba unitaria para saneamiento de tokens</name>
  <files>[tests/test_startup_lock.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_startup_lock.py)</files>
  <action>Agregar `test_settings_token_stripping` que instancie la clase `Settings` inyectando un token con espacios al inicio y saltos de línea al final ('\n EAAT... \r'), y asegure que se sanee correctamente sin disparar RuntimeError.</action>
  <verify>Ejecutar pytest tests/test_startup_lock.py.</verify>
  <done>El test pasa de forma exitosa.</done>
</task>
