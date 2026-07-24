# PYTEST AUTOPSY — FIX CATALOG & PROFILE 001 (AMPLIADO)

**Ticket:** BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-23
**Resultado:** ✅ SUCCESS — Suite **501 passed + 2 subtests**, RuntimeWarning gate verde, Coherence Score **1.000** (≥ 0.95), smoke forense de producción verde. **PENDIENTE certificación del Auditor.**

---

## 1. Resumen Ejecutivo

Se ejecutaron los 5 fixes del ticket (Milestone 3 - Etapa 4: Corrección de Flujo Post-Reset) sobre `app/services/ai_brain.py`, con diagnósticos corregidos por el Ingeniero Plan (el diagnóstico forense original fue refutado empíricamente: `search_items("Boxer")` SÍ retorna `[TVS SPORT 100 ELS, TVS SPORT 100 KLS]` con datos de producción; las causas reales estaban en la compuerta de herramienta, la resiliencia Gemini y el schema de extracción).

**Archivos tocados:**
| Archivo | Cambio |
| :--- | :--- |
| `app/services/ai_brain.py` | FIX-1, FIX-2A, FIX-2B, FIX-4A, FIX-4B (único archivo de producción modificado) |
| `tests/test_fix_catalog_profile_001.py` | **Creado** — 14 pins (5 fixes) |
| `tests/test_agentic_loop_async.py` | 1 aserción ajustada con **aprobación explícita del Auditor** (ver §4) |

Cero cambios a: lógica de catálogo (`search_items`, scoring, perímetros 163/167/168/170), flujo del embudo (PASOS 1-5, `_determine_funnel_phase`), texto verbatim de `_fallback_response`, fallback del router (Juez/`JUDGE_CRITICAL_ERROR` y su orden send≺save pineado LAT-3), firmas pineadas Wave 05-03/05-05, `required` del EXTRACTION_SCHEMA.

## 2. Fixes ejecutados y evidencia

### FIX-1 (AMPLIADO) — Compuerta forzada con alias searchBy dinámicos
- Nuevo helper `CerebroIA._load_searchby_aliases()`: carga TODOS los valores únicos de `searchBy` desde `CatalogService._items` (lowercase, sorted, dedup). Filtros de seguridad para el substring-gate: `len >= 3`, no puramente numérico, stopwords funcionales (`sin`, `con`, `one`, `new`, `life`, `abs`, `cbs`) — `'sin'` colisionaba con "sin cuota inicial"; `'abs'` con "abstracta/absoluto"; `'one'` con "presione".
- Snapshot en `__init__` (`self._searchBy_aliases`) + **refresh por turno** en `_generate_with_retry_async` (honra `/refresh_catalog` sin redespliegue — propiedad dinámica del ticket).
- `motorcycle_keywords` = base_keywords + alias de categoría + `_get_competitor_brands()` + `_searchBy_aliases` (deduplicado).
- **Pins:** `test_fix1_load_searchby_aliases_filters_and_collects` (filtros/dedup/fail-open), `test_fix1_forced_turn_fires_for_searchby_only_reference` ("Eco Deluxe 100" solo-searchBy → turno forzado con instrucción OBLIGADO + pivote a la alternativa verificada).
- **Smoke producción:** 33 alias dinámicos cargados (`boxer`, `pulsar`, `discover` ✓; `sin` y numéricos filtrados ✓); `search_items('Boxer')` → Sport 100 ELS/KLS ✓.

### FIX-2A — Timeout de cliente Gemini
- Constante de módulo `GEMINI_CALL_TIMEOUT_S = 25.0` (parcheada en tests, no def-time default).
- `_call_gemini_with_retry_async`: `asyncio.wait_for(func(...), timeout=...)` en TODA llamada (inferencia y extracción de resumen); `asyncio.TimeoutError`/`TimeoutError` añadidos al conjunto reintentable (mismo backoff exponencial 429/503).
- **Pins:** `test_fix2a_timeout_retries_and_propagates` (hang → 4 llamadas + 3 backoffs + TimeoutError final), `test_fix2a_success_within_timeout_returns_value` (1 llamada, valor intacto).

### FIX-2B — Presupuesto de reintentos para transitorios
- En el bucle externo `for attempt in range(max_retries)` de `_generate_with_retry_async`:
  - Excepción de inferencia con firma **5xx/internal** → `continue` con backoff forense (antes: fallback inmediato).
  - **Candidatos vacíos** post-inferencia y en turno forzado (safety filter transitorio) → `continue` (antes: fallback inmediato).
  - Fallback solo tras agotar `max_retries=3` (cae en la rama heredada de "Maximum retries reached" — texto verbatim intacto).
  - `RuntimeError` y demás genéricas **conservan retorno inmediato** (protege pins heredados con `side_effect`); `InvalidArgument` (400) sigue con `break`.
- **Pins:** (i) vacíos→éxito en 2 llamadas sin "colgado"; (ii) vacíos persistentes → "colgado" tras exactamente 3 llamadas; (iii) 5xx→éxito en 2 llamadas; (iv) RuntimeError → "colgado" en 1 llamada (comportamiento heredado).

### FIX-4A — EXTRACTION_SCHEMA perfilamiento
- 5 campos STRING con bias negativo estricto, **fuera de `required`**: `ingresos_mensuales`, `gastos_mensuales`, `plan_celular`, `tiene_gas_natural`, `mora_y_paz_salvo`.
- Fluyen por `_merge_extracted_data` sin tocar guardarraíles (ninguno es `_CRM_PROTECTED_FIELDS`; `_is_field_valid` rechaza vacíos/"null"/None).
- **Censo pre-fix (producción, 9 prospectos):** los 5 campos en **0/9** docs; `ocupacion`/`datacredito`/`vivienda`/`servicios_publicos` en 1/9.
- **Pins:** presencia+tipo+no-required en schema; persistencia 1:1 en merge; rechazo de valores inválidos.

### FIX-4B — Checklist determinista de perfilamiento
- Nuevo `CerebroIA._build_profiling_checklist(prospect_data)`: renderiza `<estado_perfilamiento>` con las 8 filas de la MATRIZ_PERFILAMIENTO (`CAPTURADO(valor)`/`PENDIENTE`) + `<siguiente_pendiente>`. Mapeo documentado: Ocupación y Contrato ← `ocupacion` (schema las fusiona); Ingresos ← `ingresos_mensuales`; Datacrédito ← `datacredito`; Gastos ← `gastos_mensuales`; Gas ← `tiene_gas_natural` | 'gas' en `servicios_publicos`; Vivienda ← `vivienda`; Plan ← `plan_celular` | 'celular'/'plan' en `servicios_publicos`.
- Inyección en el prompt SOLO cuando `phase == "PHASE_3_CREDIT_PROFILING"` + mandato verbatim: "PROHIBIDO repreguntar los marcados como CAPTURADO...".
- **Pins:** render parcial (✅/❌ + siguiente), render completo (COMPLETO) y vacío (8 PENDIENTE), inyección presente en PHASE_3 y ausente en PHASE_1.

## 3. Gates de verificación

| Gate | Resultado |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/ -q` | ✅ **501 passed, 2 subtests passed** (89s) |
| `.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning` | ✅ **501 passed, 2 subtests passed** (87s) |
| `npx agent-cli eval` | ✅ **Score 1.000** (506 passed, 2 skipped; umbral 0.95) |
| Smoke forense producción (solo lectura) | ✅ 33 alias dinámicos; `search_items('Boxer')` → `[TVS SPORT 100 ELS, TVS SPORT 100 KLS]`; `search_items('Eco Deluxe 100')` → vacío (sin equivalencia — correcto, no existe) |
| Pins nuevos del ticket | ✅ **14/14** en `tests/test_fix_catalog_profile_001.py` |

## 4. Pin heredado ajustado (APROBACIÓN EXPLÍCITA DEL AUDITOR)

`tests/test_agentic_loop_async.py::test_perimeter_short_tokens_and_greeting_bypass` (caso "ninja 500"):
- **Conflicto:** el mock de Gemini responde texto puro SIN llamar `search_catalog` (alucina "Kawasaki" + `$32.000.000` sin grounding). Con FIX-1, `"ninja"` (presente SOLO en el `searchBy` del ítem inyectado por el propio test) entra a `motorcycle_keywords` → la compuerta fuerza el turno de validación → `calls_made` 1→2.
- **Decisión del Auditor:** aprobar ajuste del conteo con comentario forense. El propósito del pin (perímetro de tokens cortos + greeting bypass) se preserva íntegro; el caso "benom 14" sigue en 1 llamada ("venom" no es substring de "benom").
- **Diferencia de comportamiento certificada como DESEADA:** el turno extra intercepta exactamente la alucinación que el mock simula.

## 5. Hallazgos y notas para el Auditor

1. **Diagnóstico forense original refutado (3/3):** el catálogo sí busca en `searchBy` (probado contra producción); el "colgado" no era timeout de herramienta (la búsqueda es local en memoria) sino transitorios de Gemini sin presupuesto de reintento; el estado de perfilamiento SÍ se inyectaba (`<datos_ya_capturados>`) pero el schema omitía 5 de 8 datos (censo 0/9) y no existía checklist determinista.
2. **`_load_searchby_aliases` fail-open:** cualquier corrupción de `_items` retorna `[]` y la compuerta conserva su comportamiento previo (Zero-Silent-Failures con `logger.exception`).
3. **FIX-2C diferido** (turno final forzado sin herramientas tras agotar `max_turns`): fuera de alcance por decisión del aprobador; L1712/1724/1797/2447 conservan retorno inmediato.
4. **Post-deploy recomendado (48h):** re-censar campos nuevos en `prospectos` y verificar en logs `[RETRY-5XX]`/`[RETRY-EMPTY-CANDIDATES]` que los transitorios se absorben sin "colgado" visible.

---

**ESTADO:** Build completo. DETENIDO a la espera de certificación del Auditor.
