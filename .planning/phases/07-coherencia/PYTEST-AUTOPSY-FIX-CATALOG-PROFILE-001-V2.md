# PYTEST AUTOPSY — FIX CATALOG & PROFILE 001 AMPLIADO **v2** (Instrucciones Obsoletas)

**Ticket:** BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO-v2
**Rol:** OPENCODE BUILDER (Ingeniero Build)
**Fecha:** 2026-07-24
**Resultado:** ✅ SUCCESS — Suite **506 passed + 2 subtests**, RuntimeWarning gate verde, Coherence Score **1.000** (≥ 0.95). **PENDIENTE certificación del Auditor.**

---

## 1. Resumen Ejecutivo

Se ejecutaron los 3 fixes del ticket (alcance aprobado por el Auditor en BOT-PLAN-CLARIFICATION-OBSOLETE-INSTRUCTIONS-002: FIX-A + FIX-B + FIX-C; excluidos FIX-D → v2.1 y FIX-E → ticket de configuración) sobre `app/services/ai_brain.py`, erradicando las instrucciones obsoletas que causaban los Problemas 3 y 4 del Auditor (saludo repetitivo '¡Hola Carlos!' durante la matriz + bloqueo de ~3 minutos con fallback).

**Archivos tocados:**
| Archivo | Cambio |
| :--- | :--- |
| `app/services/ai_brain.py` | FIX-A, FIX-B, FIX-C (único archivo de producción modificado) |
| `tests/test_fix_catalog_profile_001_v2.py` | **Creado** — 5 pins (3 fixes) |

Cero cambios a: lógica del embudo (`_determine_funnel_phase`, fases, transiciones), CIERRE DE FASE y rama de ejecución de la herramienta (L2222-2624), FIX-4A (EXTRACTION_SCHEMA) y FIX-4B (`_build_profiling_checklist` + inyección), `_fallback_response` (verbatim), `max_turns`, rechazos de herramienta PHASE_1/FAQ_ONLY, `prompts.py`, `personality.json`, Firestore.

## 2. Fixes ejecutados y evidencia

### FIX-A (CRÍTICO) — Instrucción obsoleta de PHASE_3_CREDIT_PROFILING (L1616-1623)
- **Erradicada:** "Ejecuta la herramienta calculate_credit_score. ¡DETENTE AQUÍ!…" (artefacto de la era Cognitive Brakes, commit `77cb4e1`). Se re-inyectaba en el XML (L1722), en máxima recencia (L1767-1768) y en cada `function_response` (L2553/2613/2620) → bucle de herramientas → `max_turns=3` → fallback (Problema 4).
- **Reemplazo (verbatim Auditor):** "Habeas Data Aceptado. Procede con la MATRIZ DE PERFILAMIENTO (8 datos). Haz SOLO UNA PREGUNTA A LA VEZ. NO repitas saludos. NO repreguntes datos CAPTURADOS. Cuando los 8 datos estén completados, ejecuta el CIERRE DE FASE según el puntaje."
- Las re-inyecciones heredadas (L1722/L1767-1768/L2553/2613/2620) NO se tocaron: con el texto corregido pasan a ser refuerzo coherente (pin 2 lo certifica en el eco de herramienta).
- **Pins:** `test_fixa_phase3_closing_instruction_is_matrix_cierre_not_detente` (bloque `<instruccion_de_cierre>` contiene MATRIZ/CIERRE y cero residuos), `test_fixa_tool_echo_in_phase3_carries_matrix_instruction_not_detente` (el `function_response` arrastra la instrucción nueva, que no induce re-ejecución).

### FIX-B (ALTA) — CRITICAL IDENTITY RULE condicionada por fase (L1779-1781)
- **Causa raíz Problema 3:** la regla v8.3 ordenaba "Tu respuesta DEBE empezar con un saludo personalizado" CADA turno con nombre conocido, en la ventana de máxima recencia, contradiciendo "PROHIBIDO REPETIR SALUDOS" de la MATRIZ (prompt Firestore).
- **Implementación:** si `phase == "PHASE_3_CREDIT_PROFILING"` → se inyecta "[PROHIBIDO repetir saludos ni el nombre del cliente al inicio durante la MATRIZ DE PERFILAMIENTO. Ve directo al punto con la siguiente pregunta pendiente.]"; en cualquier otra fase → regla v8.3 **verbatim intacta**.
- **Pins:** `test_fixb_phase3_suppresses_identity_rule_and_injects_anti_greeting`, `test_fixb_identity_rule_verbatim_outside_phase3` (regresión PHASE_1 y PHASE_2 con el string exacto).

### FIX-C (MEDIA) — Descripción de `calculate_credit_score` (L1346)
- **Erradicados:** "¡DETENTE AQUÍ! No generes respuesta." (co-causante del bucle sin texto final) y "Úsala inmediatamente después del Paso 9." ('Paso 9' inexistente en todo flujo vigente: PASOS 1-5 + MATRIZ + CIERRE).
- **Reemplazo (propuesta Planner, pendiente certificación Auditor):** declara las dos únicas ventanas de uso — (1) primera solicitud de cuotas/simulación (backend completa defaults) y (2) CIERRE DE FASE tras completar los 8 datos — y prohíbe ejecutarla en cada turno de la matriz. Sin numeración de pasos para no acoplar el código a la divergencia prompt-vs-docx (ticket §5).
- **Intactos:** `name`, TODOS los `parameters` (incluye campos FIX-4A), `required`.
- **Pin:** `test_fixc_credit_tool_description_has_usage_windows_no_paso9_no_detente` (inspecciona el `FunctionDeclaration` real vía `_create_tools` + integridad de parámetros).

## 3. Gates de verificación

| Gate | Resultado |
| :--- | :--- |
| `.venv/bin/python -m pytest tests/ -q` | ✅ **506 passed, 2 subtests passed** (86s) — eran 501 + 5 pins nuevos |
| `.venv/bin/python -m pytest tests/ -q -W error::RuntimeWarning` | ✅ **506 passed, 2 subtests passed** (86s) |
| `npx agent-cli eval` | ✅ **Score 1.000** (511 passed, 2 skipped; umbral 0.95) |
| Pins nuevos del ticket | ✅ **5/5** en `tests/test_fix_catalog_profile_001_v2.py` |
| Regresión pins v1 | ✅ **14/14** de `test_fix_catalog_profile_001.py` verdes sin modificación |

## 4. Notas forenses para el Auditor

1. **Alcance quirúrgico de los pins anti-'DETENTE':** el system instruction de fallback (`personality.json` / `prompts.py` PASO 4) aún contiene "¡DETENTE AQUÍ!" — lado PROMPT (Firestore), **excluido** del ticket (ex-FIX-E, configuración). Los pins acotan la ausencia de 'DETENTE' al bloque `<instruccion_de_cierre>` y al eco de herramienta, nunca al prompt completo. Si el ticket de configuración limpia el PASO 4 del prompt, puede endurecerse el pin a prompt-completo.
2. **Post-procesador de respuestas:** se observó que el pipeline recorta muletillas iniciales ("Entendido.") del texto final; comportamiento heredado, intacto, no relacionado con los fixes.
3. **Warnings benignos en tests sin Firestore:** `[SYNONYM INJECTION]` / `[COMPETITOR BRANDS]` / `[CATALOG_ALIASES]` degradan fail-open sin cliente Firestore (diseño Zero-Silent-Failures con log, heredado).
4. **Divergencias documentadas NO tocadas (ticket §5):** entidad 'Crediorbe' en PASO 2 de `personality.json` (fallback #2) y numeración de pasos prompt-vs-docx → ticket de configuración.
5. **Post-deploy recomendado (48h):** E2E matriz completa 8/8 → CIERRE DE FASE sin fallback ni saludo repetido; revisar logs `[FULL PROMPT AUDIT]` confirmando ausencia de 'DETENTE' en `<instruccion_de_cierre>` durante PHASE_3.

---

**ESTADO:** Build completo. DETENIDO a la espera de certificación del Auditor.
