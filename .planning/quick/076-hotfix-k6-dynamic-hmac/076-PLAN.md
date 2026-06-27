---
task: 076
name: hotfix-k6-dynamic-hmac
description: Reemplazar firma HMAC estática en test_k6.js por cálculo dinámico con crypto de k6
---

# Quick Task 076: hotfix-k6-dynamic-hmac

## Objective
Corregir el fallo criptográfico HTTP 401/403 en el gate de rendimiento k6 causado por una firma X-Hub-Signature-256 hardcodeada que no coincide con el payload aleatorio generado en cada iteración.

## Análisis de Causa Raíz
- **Archivo**: `tests/performance/test_k6.js` línea 42
- **Defecto**: La firma `sha256=mocked_k6_load_test_signature_pass_bypass` es estática pero el `payload` contiene `Math.random()` (línea 27-28), por lo que cada iteración genera un body distinto cuya firma HMAC jamás coincidirá con el hardcode.
- **Contrato del servidor** (`app/routers/whatsapp.py` L159-163): `sha256=` + `hmac.new(secret, body, sha256).hexdigest()`
- **Secret del servidor** (`app/core/config.py` L38): `os.getenv("WHATSAPP_APP_SECRET", "***REMOVED***")`

## Tasks

<task type="auto">
  <name>Inyectar firma HMAC dinámica en test_k6.js</name>
  <files>tests/performance/test_k6.js</files>
  <action>
    1. Importar `import crypto from 'k6/crypto';` al inicio del archivo
    2. Capturar secret: `const secret = __ENV.WHATSAPP_APP_SECRET || '***REMOVED***';`
    3. Después de `JSON.stringify(...)`, calcular: `const signature = crypto.hmac('sha256', secret, payload, 'hex');`
    4. Reemplazar el hardcode en `X-Hub-Signature-256` con: `'sha256=' + signature`
  </action>
  <verify>grep -n "crypto.hmac" tests/performance/test_k6.js && grep -n "mocked_k6_load_test_signature_pass_bypass" tests/performance/test_k6.js; echo "Exit: $?"</verify>
  <done>crypto.hmac aparece en el archivo y el hardcode estático NO aparece</done>
</task>

---
*Created: 2026-06-27*
