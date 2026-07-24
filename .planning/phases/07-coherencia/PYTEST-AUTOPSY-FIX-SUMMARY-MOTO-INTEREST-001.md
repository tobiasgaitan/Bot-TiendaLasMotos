# PYTEST AUTOPSY — FIX SUMMARY MOTO INTEREST 001 (REGLA DE PIVOTE)

**Ticket:** BOT-BUILD-FIX-SUMMARY-MOTO-INTEREST-001
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-24
**Resultado:** ✅ SUCCESS — Suite **511 passed + 2 subtests**, RuntimeWarning gate verde, Coherence Score **1.000** (≥ 0.95). **PENDIENTE certificación del Auditor.**

---

## 1. Resumen Ejecutivo

Se ejecutó FIX-SUMMARY-1 sobre `app/services/ai_brain.py`, corrigiendo la pérdida total de contexto tras mención de competencia: la regla de extracción de `moto_interest` en el prompt de `generate_summary` ordenaba *"Si el usuario menciona una marca de la competencia, déjalo vacío o no la extraigas"* — anulando el pivote a equivalentes del catálogo (FIX-1: Boxer → TVS Sport 100) y dejando Firestore sin `moto_interest` tras el primer turno de competencia.

**Archivos tocados:**
| Archivo | Cambio |
| :--- | :--- |
| `app/services/ai_brain.py` | FIX-SUMMARY-1: 1 línea reemplazada (verbatim del ticket) en el prompt de `generate_summary` (único cambio de producción) |
| `tests/test_fix_summary_moto_interest_001.py` | **Creado** — 2 pins (estático + integración) |

Cero cambios a: EXTRACTION_SCHEMA (campos y `required` intactos), `_call_gemini_with_retry_async`, `clean_json_voorhees`, reglas 1/3/4 del prompt extractor (habeas/resumen/moto_confirmada), **[REGLA DE PERSISTENCIA - MOTO DE INTERÉS]** (mecanismo complementario intacto: protege la moto ya en DB; la REGLA DE PIVOTE cubre el primer turno de competencia con DB vacía).

## 2. Fix ejecutado y evidencia

### FIX-SUMMARY-1 (CRÍTICO) — REGLA DE PIVOTE (L2746)
- **Erradicada:** `- PROHIBIDO guardar marcas de la competencia como Bajaj, Yamaha, Honda, Suzuki, AKT. Si el usuario menciona una marca de la competencia, déjalo vacío o no la extraigas.` (ocurrencia única verificada por grep en todo `app/`).
- **Reemplazo (verbatim ticket):** `- REGLA DE PIVOTE: Si el usuario menciona una marca de la competencia (ej. Boxer, NKD) pero el bot ofreció un equivalente del catálogo (ej. TVS Sport 100), DEBES extraer el modelo del catálogo ofrecido (TVS Sport 100), NO la marca de competencia. Solo déjalo vacío si no hay NINGUNA moto del catálogo mencionada o recomendada en la conversación.`
- **Se conserva** la guarda anti-competencia superior: `Este campo es INMUTABLE contra la competencia. Solo guarda modelos de Tienda Las Motos.` (L2745).
- **Pins (2/2 verdes):**
  - `test_fix_summary1_prompt_carries_pivot_rule_and_not_obsolete_wipe` — el prompt enviado a Gemini porta la REGLA DE PIVOTE completa, cero residuos de la orden obsoleta ("déjalo vacío o no la extraigas" / "PROHIBIDO guardar marcas de la competencia"), y conserva INMUTABLE + REGLA DE PERSISTENCIA.
  - `test_fix_summary1_competitor_pivot_persists_catalog_moto_interest` — escenario del ticket: historial `¿Tienen la Boxer CT 100?` + pivote del bot a `TVS Sport 100 ELS` + solicitud de cuota → `generate_summary` devuelve `moto_interest="TVS Sport 100"` (no vacío, no competencia) y el extractor recibió la regla con el historial del pivote.

## 3. Gates de verificación

| Gate | Resultado |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/ -q` | ✅ **511 passed, 2 subtests passed** (84s) — eran 509 + 2 pins nuevos |
| `.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning` | ✅ **511 passed, 2 subtests passed** (84s) |
| `npx agent-cli eval` | ✅ **Score 1.000** (516 passed, 2 skipped; umbral 0.95) |
| Pins nuevos del ticket | ✅ **2/2** en `tests/test_fix_summary_moto_interest_001.py` |
| Regresión pins v1+v2+matrix | ✅ **21/21** verdes sin modificación (incluye `test_firestore_nomenclature_extraction.py`, cuyo patrón de mock se reutilizó) |

## 4. Notas forenses para el Auditor

1. **Sinergia con REGLA DE PERSISTENCIA (intacta):** los dos mecanismos son complementarios y no se solapan — PERSISTENCIA re-incluye la moto ya en DB (`previous_moto_interest`); PIVOTE cubre el primer turno de competencia (DB vacía) extrayendo el equivalente ofrecido por el bot. La condición de escape del PIVOTE ("vacío solo si no hay NINGUNA moto del catálogo mencionada") mantiene el bias negativo para chats sin interés real.
2. **Pin estático + integración (precedente FIX-MATRIX-RESTART-001):** el compliance del extractor LLM es probabilístico; la verificación empírica del pivote real queda en el gate post-deploy.
3. **Post-deploy recomendado (48h):** E2E `¿Tienen la Boxer?` → `¿Cuota?` → verificar Firestore `moto_interest` = modelo TVS/Victory persistido tras cada turno y que el Turno 2 continúa el embudo (no reinicia catálogo). Revisar logs `🧠 [RAW LLM SUMMARY OUTPUT]` para confirmar el campo en el JSON.

---

**ESTADO:** Build completo. DETENIDO a la espera de certificación del Auditor.
