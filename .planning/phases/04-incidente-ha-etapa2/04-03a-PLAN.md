---
phase: 04
plan: 04-03a
name: Erradicación del Bypass is_test_mode en Producción
wave: 3
depends_on: [04-02]
files_modified: [app/routers/whatsapp.py, app/main.py, app/services/catalog_service.py, app/core/config.py, tests/conftest.py, .github/workflows/qa-pipeline.yml]
requirements: [HA-2]
---

# Plan 04-03a: Erradicación del Bypass is_test_mode en Producción

## Objective
Eliminar TODOS los seams `is_test_mode`/`TEST_MODE`/`"pytest" in sys.modules` del código de producción y del arnés global. El STARTUP-GUARD pasa a ser estricto e incondicional; los tests lo satisfacen con el mocking dinámico de 04-02. CONSTRAINT ABSOLUTA: NO tocar `app/services/ai_brain.py` ni copywriting de `juan_pablo_personality` (verificado: ai_brain.py NO contiene bypass — no requiere cambios).

## Code Patterns (Model Resilience)
- `app/routers/whatsapp.py` L405-445 y L520-555 — bloques gemelos del guard (mantenerlos estructuralmente idénticos tras la edición)
- `app/main.py` L71-185 — lifespan con rama TEST_MODE (la rama de producción es la única que sobrevive)
- Zero-silent-failures: TODO try/except tocado DEBE inyectar `logger.exception(...)`

## Tasks

<task type="auto">
  <name>T1 — Guard estricto en whatsapp.py (2 sitios)</name>
  <files>app/routers/whatsapp.py</files>
  <action>
    1. En `webhook_handler` (~L419) y `task_processor` (~L525), eliminar: `is_test_mode = ...`, el sniffing de tipo Mock (`type(min_items_val).__name__ in (...)`), y `should_bypass`.
    2. Sustituir por parseo estricto:
       ```python
       try:
           min_items = int(settings.min_catalog_items)
       except (TypeError, ValueError) as e:
           logger.exception(f"❌ [STARTUP-GUARD] min_catalog_items inválido ({settings.min_catalog_items!r}): {e}")
           min_items = 60
       ```
    3. Guard incondicional: `if not catalog_ready or catalog_items_count < min_items:` → log error + HTTPException 503 (texto existente se conserva).
    4. Eliminar imports huérfanos (`sys` si queda sin uso en el archivo — verificar antes de quitar).
  </action>
  <verify>`./.venv/bin/python -m py_compile app/routers/whatsapp.py` + `./.venv/bin/pytest tests/test_webhook_sync_block.py -q`</verify>
  <done>Cero ramas de bypass; guard idéntico en ambos endpoints; except con logger.exception</done>
</task>

<task type="auto">
  <name>T2 — Lifespan único en main.py</name>
  <files>app/main.py</files>
  <action>
    1. Eliminar `TEST_MODE = os.getenv("TEST_MODE") == "true" or "pytest" in sys.modules` (L71).
    2. En lifespan: eliminar la rama `else:` (inline init con mocks, L110-185) y el fallback `if os.getenv("TEST_MODE") == "true": ... DummyConfigLoader`; conservar SOLO la rama de producción (`app.state.startup_task = asyncio.create_task(_run_deferred_initialization(app))`).
    3. Los except que sobreviven conservan/añaden `logger.exception`.
    4. Eliminar imports que queden huérfanos (p. ej. `get_firebase_credentials_object`, `firestore`, `ConfigLoader`, `FinanceConfigLoader`, `storage_service`, `init_memory_service`, `config_service`, `catalog_service` SI solo los usaba la rama muerta — verificar con grep antes de remover cada uno).
  </action>
  <verify>`./.venv/bin/python -m py_compile app/main.py` + `./.venv/bin/pytest tests/test_startup_lock.py tests/test_health_check.py -q` verde (estos tests YA ejercitan la rama real vía startup_task)</verify>
  <done>Un solo camino de inicialización; módulo compila; tests de lifespan verdes</done>
</task>

<task type="auto">
  <name>T3 — Padding por settings en catalog_service.py</name>
  <files>app/services/catalog_service.py</files>
  <action>
    1. Eliminar `import sys`/`is_test = os.getenv(...)` del bloque STARTUP-GUARD-PAD (~L443-450).
    2. `target_min = int(settings.min_catalog_items)` con try/except + `logger.exception` (fallback 60).
    3. Condición final: `if target_min > 0 and 0 < len(temp_items) < target_min:` → padding hasta target_min (comportamiento producción idéntico: 60; en tests, MIN_CATALOG_ITEMS controla explícitamente — sin detección de pytest).
    4. Conservar comentario WHY actualizado (sin referencia a "test mode").
  </action>
  <verify>`./.venv/bin/pytest tests/test_catalog_double_buffer.py tests/test_catalog_initialization_sync.py -q` verde</verify>
  <done>Padding gobernado por settings, no por detección de pytest; comportamiento prod inalterado</done>
</task>

<task type="auto">
  <name>T4 — Default uniforme en config.py</name>
  <files>app/core/config.py</files>
  <action>
    1. L83: `default_min_items = "0" if "pytest" in sys.modules else "40"` → `default_min_items = "40"`.
    2. Eliminar `import sys` si queda huérfano (verificar otros usos en el archivo).
    3. `tests/test_min_catalog_items_env.py`: actualizar el test del default para asertar 40 sin rama pytest (eliminar `assert settings_inst.min_catalog_items == 0` bajo pytest y el caso "no_pytest" duplicado; un solo caso: default 40).
  </action>
  <verify>`./.venv/bin/pytest tests/test_min_catalog_items_env.py -q` verde</verify>
  <done>Settings libre de introspección de pytest</done>
</task>

<task type="auto">
  <name>T5 — Arnés global y CI sin bypass</name>
  <files>tests/conftest.py, .github/workflows/qa-pipeline.yml</files>
  <action>
    1. conftest.py `mock_env_vars`: quitar `"TEST_MODE": "true"` y `"MIN_CATALOG_ITEMS": "0"` (los tests que necesiten catálogo usan los fixtures de 04-02).
    2. qa-pipeline.yml: quitar `TEST_MODE: "true"` y `MIN_CATALOG_ITEMS: "0"` del job y su comentario asociado (L14-19 aprox).
    3. `tests/test_config_startup.py`: eliminar `"MIN_CATALOG_ITEMS": "0"` de su patch.dict si quedara (usa fixtures ahora).
  </action>
  <verify>`rg -n "is_test_mode|TEST_MODE|pytest.{0,20}sys\.modules" app/ tests/conftest.py tests/test_config_startup.py .github/` = 0 hits (acceptance #2)</verify>
  <done>Seam erradicado de código, arnés y CI</done>
</task>

<task type="auto">
  <name>T6 — Suite completa + Coherence gate de wave</name>
  <files>—</files>
  <action>
    1. `./.venv/bin/pytest -q` completo — DEBE estar verde; cualquier test que dependiera del bypass se migra a fixtures (dentro de esta tarea, no se pospone).
    2. `npx agent-cli eval` → Coherence Score ≥ 0.9 (prerequisito explícito de 04-03b). Pegar salida real en SUMMARY.
  </action>
  <verify>pytest verde + eval ≥ 0.9 con salida real</verify>
  <done>04-03a certificada; desbloquea 04-03b</done>
</task>

## Must-Haves
- [ ] `rg "is_test_mode|TEST_MODE|pytest.{0,20}sys\.modules" app/ tests/conftest.py .github/` = 0 hits
- [ ] Guard STARTUP estricto e idéntico en webhook_handler y task_processor
- [ ] Lifespan de un solo camino; padding por settings; default 40 uniforme
- [ ] ai_brain.py y juan_pablo_personality SIN modificaciones (git diff vacío)
- [ ] Todo except tocado tiene logger.exception
- [ ] Suite verde + Coherence ≥ 0.9

---
*Created: 2026-07-22 | Incidente H-A · BOT-BUILD-INCIDENT-HA-201*
