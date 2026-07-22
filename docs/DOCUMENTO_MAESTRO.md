# 🛡️ Documento Maestro: Estado de Desarrollo Core (v10.45.40)

**Versión:** v10.45.40 (Milestone 2 Phase 1 — Multimodal CLOSED & CERTIFIED)  
**Estado:** PRODUCTION READY / GCP LIVE  
**Coherence Score:** 1.000 (Certificado vía GSD Framework - 357/357 Tests PASSED, 0 failed)

---

## 🚀 Últimos Hitos Consolidados (Línea de Producción)

*   **Cierre Certificado Milestone 2 - Phase 1 (v10.45.40):** Certificación atómica del pipeline de Similitud Multimodal e Integración (R7–R12: `match_catalog_item_by_image`, `analyze_image`/`_process_moto` JSON-first, integración webhook, suite `test_multimodal_similitude.py` 25/25). Autopsia de falso negativo del entorno documentada (intérprete sistema 3.14 vs `.venv` 3.13 → `ModuleNotFoundError: ffmpeg`), pin de entorno documentado en `README.md`, pin determinista del guardrail de inicialización en `tests/test_zombie_recovery_flow.py` (supresión del RuntimeWarning transversal de la suite) y sincronía documental PSD ejecutada (ROADMAP/REQUIREMENTS/STATE). Eval GSD: **Score 1.000 — DEPLOY AUTHORIZED** [BOT-BUILD-MULTIMODAL-CIERRE-196].
*   **Saneamiento de Credenciales (v10.45.14):** Inyección de `.strip()` agresivo en `app/core/config.py` sobre `WHATSAPP_TOKEN` y `WHATSAPP_APP_SECRET` antes de la validación. Elimina espacios residuales de la terminal y robustece `tests/test_startup_lock.py` [BOT-INFRA-BUGFIX-TOKEN-STRIP-194].
*   **Port Binding & Health Endpoint (v10.45.29):** Refactorización atómica de `/health` en `app/main.py`. Devuelve HTTP 200 OK y `{"status": "starting"}` de forma síncrona inmediata si el catálogo no se ha hidratado, previniendo caídas por timeout de Cloud Run. Desacopla la validación rígida (len >= 60) confinándola exclusivamente en los middlewares de `app/routers/whatsapp.py` [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192].
*   **Guardrail de Primer Contacto (v10.45.29):** Refactorización de `skip_greeting` en `ai_brain.py`. Impide el bypass del saludo comercial en el primer contacto o tras un `/reset` (`has_no_legitimate_history = True`). Fuerza la validación de caché mínima (`min_catalog_items = 60`) en producción con bypass controlado (`is_test_mode`) [BOT-BRAIN-BUGFIX-FIRST-CONTACT-ALIGNMENT-191].
*   **Lifespan Async Delay (v10.45.29):** Inyección de un retardo asíncrono no bloqueante estricto de 2 segundos (`await asyncio.sleep(2)`) al inicio de `_run_deferred_initialization` en `app/main.py`. Permite que Uvicorn enlace el puerto 8080 antes de levantar las conexiones pesadas de red externa [BOT-BACKEND-BUGFIX-LIFESPAN-DELAY-190].

---

## 📊 Matriz Histórica de Cambios y Estabilidad (v10.0.0 a v10.39.0)

| Versión / Ticket | Componente Afectado | Descripción del Ajuste Quirúrgico y Protección Core |
| :--- | :--- | :--- |
| **BOT-BACKEND-188** | `app/main.py` | Migración de la inicialización pesada (Firestore, Secret Manager) a un `asyncio.create_task()` background desde el lifespan handler. |
| **BOT-BACKEND-187** | `CatalogService` | Normalización fonética previa a `SequenceMatcher` en tokens cortos ($\le 5$ caracteres) y whitelist de cilindrajes (100, 125, 150, 160, 200, 500). |
| **BOT-FINANCIAL-184**| `financial_service.py`| Sincronización secuencial estricta paso a paso del flujo Brilla de Gases en Python en paridad exacta con la lógica TypeScript. |
| **BOT-FINANCIAL-181**| `Phase 3 Financial` | Omisión de cobro flat de `cuota_aval_mensual` y `seguro_vida` cuando `uso_matriz == True` para erradicar inflación de cuotas en WhatsApp. |
| **BOT-INFRA-33** | `_firestore_io` | Interceptor de I/O con `asyncio.wait_for` limitado a 5s para evitar congelamiento de sockets y mitigar ráfagas concurrentes. |
| **BOT-ROUTER-120** | `whatsapp.py` | Implementación de Locks de Sesión asíncronos (`asyncio.Lock`) por número E.164. Serializa webhooks para asegurar el commit en Firestore. |
| **BOT-INFRA-171** | `MessageBuffer` | Guardrail de idempotencia síncrona en la frontera mediante `register_wamid` con bloqueo por sesión para fulminar duplicados de Meta. |
| **BOT-PERF-41** | `CatalogService` | Caché semántica local con bypass inmediato del LLM si el score fuzzy es $\ge 0.85$, reduciendo un 100% el consumo innecesario de tokens. |
| **BOT-SEC-50** | `S-TOON_Middleware` | Jaula de Faraday virtual mediante tags `<|S_START|>` y `<|S_END|>` para blindar las entradas contra Prompt Injections estructurales. |
| **BOT-QA-LOOP-107** | `CerebroIA` | Bucle agéntico asíncrono de auto-reparación. Si falla el formato visual, reintenta automáticamente hasta $N_{\max}=3$ con temperatura 0.1. |

---

## 🏛️ Directivas Inmutables de Arquitectura

1.  **Mandato de Bloqueo CRM (`_CRM_PROTECTED_FIELDS`):** Queda estrictamente prohibido que el motor de extracción de la IA pise, degrade o modifique las cuotas financieras reales o campos manuales introducidos por el asesor comercial[cite: 3].
2.  **Zero-Silent-Failures:** Queda terminantemente prohibido capturar excepciones genéricas sin inyectar un log forense estructurado completo (`logger.exception`). Toda contingencia de red o timeout debe retornar un `_ContingencySnapshot` controlado[cite: 3].
3.  **Visual-Lock (PCC Pro):** Toda respuesta que mencione una motocicleta debe incluir de forma obligatoria el precio formateado (`$`) y la imagen estructurada en Markdown nativo (`![]()`) recuperada de `search_catalog`[cite: 2, 3].
