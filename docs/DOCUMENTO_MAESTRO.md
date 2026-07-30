🛡️  Documento Maestro: Estado de Desarrollo Core (v10.50.1)
Versión: v10.50.1 (Milestone 4 — COMPLETO & CERTIFIED · H-ZOMBIE-1 purgado)
Estado: PRODUCTION READY / GCP LIVE (Beta)
Coherence Score: 1.000 (Certificado vía GSD Framework — 646/646 items puntuables PASSED, 0 failed, 0 skipped; perímetro canónico: repo completo = 646 items recolectados)

🚀  Últimos Hitos Consolidados (Línea de Producción)
1. Cierre Certificado Milestone 3 - Etapa 5 (v10.48.0): Resolución de Concurrencia y Legado. Migración de bucles de acuses (webhook_handler y task_processor) de add_task a await bloqueante con bloques de resiliencia ZSF. Erradicación de status_semaphore (YAGNI). Blindaje forense con logger.exception en fallos de red.
2. Cierre Certificado Milestone 3 - Etapa 6 (v10.48.0): Blindaje Conductual del Agente. Implementación de URL-Lock anti-alucinación (whitelist default-deny + sustitución SSOT catálogo) en egress_guard_service.py. Validadores coercitivos de longitud (4 líneas / 350 chars) con preservación de pregunta de cierre. Anclaje de contexto FAQ vs. Embudo en 3 capas.
3. Cierre Certificado Cuarentena C5 (v10.48.0): Gobernanza SSOT. Alineación de tono en BUSINESS_RULES.md a 1ª persona singular. Inserción de bloque "Gobernanza de Datos" y Directiva Inmutable #6.
4. Cierre Certificado Deudas Vivas (v10.48.1): Erradicación de doble ejecución de sesión en rama de audio (_pipeline_audio). Paridad de invariante BOT-PONYTAIL-200 en admin.py::_set_human_help_status_direct.
5. Cierre Certificado Etapa 7 (v10.49.0): Despliegue y Publicación. Push a beta exitoso, despliegue a GCP Cloud Run y publicación del paquete interno @tobiasgaitan/agent-cli@1.0.6 en GitHub Packages.
6. Cierre Certificado Milestone 4 (v10.50.0): Frente de Higiene de Arnés COMPLETO. Erradicación de contaminación import-time (H-LAT-R5, H-ARNÉS-7), eliminación de barredores manuales redundantes (H-ARNÉS-2) y teardowns manuales frágiles (H-ARNÉS-5). Núcleo M4-002 (F1-F6) permaneció congelado e intacto durante todo el frente. Score 1.000 mantenido.
7. Cierre Certificado H-ZOMBIE-1 (v10.50.1): Purga forense de 2 scripts zombie Sprint 1 (test_intent_evaluator.py + test_memory_survey_state.py; tests de código eliminado en c4599e2 — métodos bajo prueba evaluate_survey_intent y MemoryService.*_survey_state erradicados de producción; clasificación (a)×2: cero referencias activas, cero dependencias inversas, cero cobertura que perder, cero afectación al embudo). Denominador canónico 648→646 recolectados (7→5 scripts/); 2→0 skipped. Score 1.000 mantenido. Núcleo M4-002 intacto.

📐  Gobernanza de Métricas de Coherencia (M4-003)
Perímetro canónico: el repositorio completo. La medición oficial es npx agent-cli eval (≡ uv run pytest --tb=no -q desde rootdir, sin testpaths): recolecta tests/ (641 items) + scripts/test_*.py (5 items) = 646 items.
Métricas, ambas sobre el MISMO perímetro canónico:
1. Deploy-Gate (operativo): Score = passed / (passed + failed) ≥ 0.900. Los skipped no puntúan. Autoriza npm publish / push a beta.
2. Coherence Score GSD (certificación): Score 1.000 exacto sobre el perímetro canónico (0 failed; skipped solo con marca explícita: integration-sin-credenciales). Certificar "1.000" con Score < 1.000 es violación ZSF documental.
Cifras canónicas (M4-003, post-purga H-ZOMBIE-1): 646 recolectados = 641 tests/ + 5 scripts/. 0 skipped. 646 items puntuables = denominador del Score. Prohibido reportar el denominador (recolectados o puntuables) como "PASSED": PASSED es exclusivamente el conteo de tests que pasaron. Las tres cifras 646 (recolectados) / 646 (puntuables) / 641 (items bajo tests/) coexisten definidas; cualquier cifra futura debe declarar su denominador.

📊  Matriz Histórica de Cambios y Estabilidad (v10.47.5 a v10.50.1)
| Versión / Ticket | Componente Afectado | Descripción del Ajuste Quirúrgico y Protección Core |
|------------------|---------------------|-----------------------------------------------------|
| H-ZOMBIE-1 (v10.50.1) | scripts/test_intent_evaluator.py, test_memory_survey_state.py | Purga de 2 scripts zombie Sprint 1 (tests de código eliminado en c4599e2). Denominador 648→646 recolectados (7→5 scripts/); 2→0 skipped. Score 1.000. |
| M4-PLAN-ARNÉS-5-004 (v10.50.0) | tests/test_agentic_loop_async.py | Eliminación pura + dedent de try/finally manual redundante ×6. STATIC-CURE-OK. |
| M4-PLAN-ARNÉS-2-003 (v10.50.0) | tests/test_config_startup.py, test_pcc... | Eliminación pura de barredores manuales (patch.stopall, sys.modules pops) redundantes con fixtures autouse. |
| M4-PLAN-ARNÉS-7-002 (v10.50.0) | tests/verify_*.py (5 archivos) | Cura vector V1 (sys.modules import-time) + eliminación SIGSEGV teardown en strict_handoff (mecanismo α). |
| M4-PLAN-LAT-R5-001 (v10.50.0) | scripts/test_phase3_faq.py | Saneamiento import-time: reubicación verbatim de init SDK/sys.exit a runtime. STATIC-CURE-OK. |
| M3-ETAPA-7 (v10.49.0) | Infraestructura / CI-CD | Despliegue a producción GCP Cloud Run. Publicación CLI v1.0.6. Score 1.000. |
| M3-DEUDA-VIVA-001 (v10.48.1) | whatsapp.py, admin.py, tests | DV-1: Eliminada duplicidad de create_prospect_if_missing en audio. DV-2: Paridad de ponytail_status en handoff de admin. |
| BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 (v10.48.0) | egress_guard_service.py, ai_brain.py, docs | URL-Lock default-deny + sustitución SSOT; coerción 4 líneas/350 chars; FIX-B, D, E; anclaje FAQ 3 capas. |

Nota M4-003 (anotación, sin corrección del registro histórico) — fila M3-ETAPA-7: bajo el estándar de medición vigente en M3-Etapa-7, la fila superior registró el denominador del eval de la época como "Score 1.000 (644 tests)". El deploy-gate real de ese hito fue Score 0.989 ≥ 0.900; el denominador de 644 correspondía a 637 passed + 7 failed + 2 skipped, y los 7 failed eran contaminación por scripts/test_v25_audio.py (H-ARNÉS-6), erradicada en M4-003. La definición vigente de métricas —que distingue denominador de PASSED y deploy-gate de Coherence 1.000— está en el bloque "📐 Gobernanza de Métricas de Coherencia (M4-003)". Esta nota preserva el registro histórico intacto y añade el contexto forense; no modifica la fila.

🏛️  Directivas Inmutables de Arquitectura
1. Mandato de Bloqueo CRM (_CRM_PROTECTED_FIELDS): Prohibido que el motor de extracción de la IA pise, degrade o modifique las cuotas financieras reales o campos manuales introducidos por el asesor comercial.
2. Zero-Silent-Failures: Prohibido capturar excepciones genéricas sin inyectar un log forense estructurado completo (logger.exception). Toda contingencia de red o timeout debe retornar un _ContingencySnapshot controlado.
3. Visual-Lock (PCC Pro): Toda respuesta que mencione una motocicleta debe incluir obligatoriamente el precio formateado ($) y la imagen estructurada en Markdown nativo (![]()) recuperada de search_catalog.
4. REGLA DE PIVOTE (v10.47.4): Si el usuario menciona marca de competencia pero el bot ofrece equivalente del catálogo, el extractor DEBE persistir el modelo del catálogo en moto_interest, NO dejar vacío.
5. Mapeo Semántico de Ingresos (v10.47.3): El extractor DEBE mapear expresiones coloquiales a valores numéricos exactos. Bias negativo: vacío SOLO si no se mencionaron ingresos.
6. Gobernanza de Fuentes de Verdad (v10.48.0): SSOT Documental = docs/DOCUMENTO_MAESTRO.md. SSOT de Ejecución = campo searchBy del catálogo en Firestore + prompt juan_pablo_personality. En caso de divergencia, prevalece siempre el SSOT de Ejecución.

📋  Estado Actual del Embudo Comercial "Juan Pablo"
PASO 1 (Enganche de Valor): Saludo condicional + search_catalog + Visual-Lock (imagen + precio). Pivote de competencia habilitado.
PASO 2 (Simulación Ciega Anticipada): calculate_credit_score con datos ciegos (Brilla de Gases, SMLV, 10% inicial). Timeout 25s + reintentos.
PASO 3 (Entrega de Cuota Enganche): Lectura de JSON + entrega de cuota aproximada (24 meses) + script de Habeas Data.
PASO 4 (Muro Legal): Autorización de política de privacidad (Ley 1581). habeas_data_accepted → true.
PASO 5 (Identidad y Transición): Nombre + Ciudad (Sanitize PII: 50 chars máx). Transición a MATRIZ_DE_PERFILAMIENTO_ESTRICTA.
MATRIZ (8 datos): Ocupación → Contrato → Ingresos (mapeo semántico) → Datacrédito → Gastos → Gas Natural → Vivienda → Plan Celular. Checklist determinista.
CIERRE DE FASE: Evaluación de puntaje → 4 rutas (Banco de Bogotá ≥750, Revisión humana 500-749, Brilla <499, Rechazo <499 sin Brilla).

⚠️  Deuda Técnica Residual Documentada
1. Saludo repetitivo en matriz (cosmético) ✅ RESUELTO (v10.48.0): Guard estático por dato ocupacion truthy + supresor coercitivo de prefijo post-generación.
2. Entidad "Crediorbe" obsoleta ✅ RESUELTO Y CERRADO FORENSEMENTE (v10.48.0): sync_full_prompt.py ejecutado como CANAL ÚNICO. Triple aserción post-sync archivada.
3. Pregunta genérica en FAQ brake ✅ RESUELTO (v10.48.0): _get_pending_funnel_question PHASE_3 evalúa la matriz vía _evaluate_profiling_matrix (SSOT compartido).
4. Frente de Higiene de Arnés M4 ✅ RESUELTO Y CERRADO FORENSEMENTE (v10.50.0): H-LAT-R5, H-ARNÉS-7, H-ARNÉS-2, H-ARNÉS-5 desplegados en beta (#431 a #434). Núcleo M4-002 intacto.
5. Scripts Zombie (H-ZOMBIE-1) ✅ RESUELTO Y CERRADO FORENSEMENTE (v10.50.1 / commit 53452aa): purga de scripts/test_intent_evaluator.py + scripts/test_memory_survey_state.py (tests de código eliminado en c4599e2; métodos bajo prueba evaluate_survey_intent y MemoryService.*_survey_state erradicados de producción en Sprint 1; clasificación (a)×2: cero referencias activas, cero dependencias inversas, cero cobertura que perder, cero afectación al embudo). Denominador canónico 648→646 recolectados (7→5 scripts/); 2→0 skipped. Score 1.000 mantenido. Núcleo M4-002 intacto.
6. Deriva/Replica en verify_*.py no-portadores (H-ARNÉS-VFY-*) ⏳ VIGILANCIA PASIVA: Mutaciones runtime o variables de entorno en archivos fuera del perímetro de colección. Purga futura con prueba.

🎯  Próximos Pasos
•  ✅ Sincronización Documental (H-DOC-R5 / H-FUENTES-1) RESUELTO (v10.50.1): .docx del KB alineado con SSOT real post-purga (646/646 passed, 0 skipped; hitos M4 + H-ZOMBIE-1 registrados).
•  ✅ Decisión de Gobernanza (H-ZOMBIE-1) RESUELTO (v10.50.1 / 53452aa): purga de 2 scripts zombie ejecutada y certificada.
•  Mantenimiento de la higiene del arnés de pruebas (M4 completado; vigilancia continua).
•  Vigilancia pasiva de deudas menores de arnés (H-ARNÉS-MI / H-ARNÉS-DEAD / H-ARNÉS-VFY-*): purga futura con prueba si se reactivan.