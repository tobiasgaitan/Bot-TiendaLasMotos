---
phase: 04
plan: 04-03b
name: Migración TestClient a Lifespan Real
wave: 3b
depends_on: [04-03a]
files_modified: [tests/test_startup_lock.py, tests/test_health_check.py, tests/test_agentic_loop_async.py, tests/test_robots.py, tests/test_api_bounds.py, tests/test_multimodal_similitude.py, tests/test_notification_service.py]
requirements: [HA-2, HA-3]
---

# Plan 04-03b: Migración TestClient a Lifespan Real

## Objective
Tras 04-03a, el lifespan ya no tiene rama TEST_MODE: toda app levantada en tests ejecuta `_run_deferred_initialization` real (background task). Los ~14 archivos que usan TestClient/httpx deben funcionar contra ese camino único mediante un fixture compartido que mockea Firestore/credenciales y ESPERA `app.state.startup_task`. Prerequisito CERTIFICADO: 04-03a con Coherence ≥ 0.9.

## Code Patterns (Model Resilience)
- `tests/test_startup_lock.py` — ya ejercita la rama real: patrón de patch de `get_firebase_credentials_object`, `firestore.Client/AsyncClient`, inicializadores de servicios y await/poll de `app.state.startup_task` + `catalog_ready`
- `tests/test_health_check.py` — manipulación explícita de `app.state.catalog_ready` con teardown cuidadoso

## Tasks

<task type="auto">
  <name>T1 — Fixture compartido `real_lifespan_client`</name>
  <files>tests/conftest.py</files>
  <action>
    1. Fixture async (o factory + TestClient según estilo del archivo consumidor) que:
       a. patch `app.main.get_firebase_credentials_object` → MagicMock
       b. patch `app.main.firestore.Client` / `firestore.AsyncClient` → MagicMock
       c. patch inicializadores pesados (`config_service.initialize`, `config_loader.load_all`, `catalog_service.initialize` con dynamic_catalog de 04-02, `FinanceConfigLoader`, `storage_service.initialize`, `init_memory_service`)
       d. levanta TestClient(app) CON lifespan (`with TestClient(app) as client:`) y hace poll de `app.state.startup_task`/`catalog_ready` con timeout 5s (patrón test_startup_lock L243-252)
    2. Teardown: restaurar `app.state` (catalog_ready, startup_task, config_loader) como hace test_health_check.
    3. WHY docstring: tras HA-2 el lifespan es de camino único; este fixture es la ÚNICA forma aprobada de levantar la app en tests.
  </action>
  <verify>`./.venv/bin/pytest tests/test_health_check.py tests/test_startup_lock.py -q` verde usando el fixture</verify>
  <done>Fixture operativo y documentado en conftest.py</done>
</task>

<task type="auto">
  <name>T2 — Migración de archivos consumidores</name>
  <files>tests/test_agentic_loop_async.py, tests/test_robots.py, tests/test_api_bounds.py, tests/test_multimodal_similitude.py, tests/test_notification_service.py (+ cualquier otro de los 14 que falle)</files>
  <action>
    1. Inventariar los 14 archivos con TestClient/httpx: `grep -rln "TestClient\|httpx\|ASGITransport" tests/ --include="*.py"`.
    2. Para cada uno: sustituir construcción ad-hoc de cliente por `real_lifespan_client` (o envolver su setup actual con los patches del fixture si tiene necesidades específicas — documentar por qué).
    3. Ejecutar cada archivo migrado de forma aislada; luego en lote.
    4. PROHIBIDO reintroducir `TEST_MODE`/`pytest in sys.modules` como atajo — cualquier test irreparablemente acoplado se reporta al usuario, no se hackea.
  </action>
  <verify>`./.venv/bin/pytest <cada archivo migrado> -q` verde individualmente</verify>
  <done>14/14 archivos funcionan contra el lifespan real</done>
</task>

<task type="auto">
  <name>T3 — Suite completa + re-certificación</name>
  <files>—</files>
  <action>
    1. `./.venv/bin/pytest -q` completo verde, 0 RuntimeWarning transversal (acceptance #4).
    2. `npx agent-cli eval` → Coherence ≥ 0.9, salida real en SUMMARY.
    3. `rg -n "is_test_mode|TEST_MODE" tests/` → solo referencias documentales en docstrings/comentarios WHY (listarlas; cero lógica).
  </action>
  <verify>pytest + eval verdes con salida real</verify>
  <done>Wave 3 cerrada; tests 100% libres del seam</done>
</task>

## Must-Haves
- [ ] Fixture real_lifespan_client en conftest.py con teardown de app.state
- [ ] 14 archivos TestClient/httpx migrados y verdes individualmente
- [ ] Suite completa verde sin RuntimeWarning transversal
- [ ] Coherence ≥ 0.9
- [ ] Cero reintroducción del seam en tests (salvo menciones documentales)

---
*Created: 2026-07-22 | Incidente H-A · BOT-BUILD-INCIDENT-HA-201*
