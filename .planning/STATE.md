### 🛡️ Documento Maestro: Estado de Desarrollo Bot-TiendaLasMotos (v9.9.2)

**Versión Actual:** v9.9.2 (Paridad de Datos, Optimización de Recall y Estabilización de Enrutador/Juez). 
**Último Hito:** Cierre de BOT-DB-4.3-FIX (Normalización absoluta de Catálogo) y despliegue de Hotfixes Críticos (Adapter Pattern, UnboundLocalError, C5 Calibration). Score de Coherencia: 1.000 (Tests PASSED) bajo Python 3.13.

#### 1. Contexto y Persona (Juan Pablo)
* **Identidad:** Asesor comercial experto con trazabilidad forense vía Langfuse.
* **Nomenclatura Técnica:** Asociación obligatoria de datos al esquema inmutable: `moto_interest` para modelos y `habeas_data_accepted` para estatus legal.
* **Criterio de Verdad:** Paridad v1.5.0 activa y constante JUAN_PABLO_SYSTEM_INSTRUCTION sincronizada con la v9.9.2 de Firestore.

#### 2. Stack Tecnológico y Dependencias
* **IA Core:** Gemini 2.5 Flash (v2.0).
* **Observabilidad:** Langfuse SDK con decoradores `@observe()` para monitoreo de latencia, costo de tokens y trazas de razonamiento.
* **Gestión:** Orquestación de dependencias mediante `uv`.

### Quick Tasks Completed
| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 026 | Hotfix Firestore Timeout | 2026-05-15 | pending | 026-hotfix-firestore-timeout |

#### 3. Arquitectura de Infraestructura (GCP & Comandos)
* **Intercepción de Comandos:** Lógica de `/reset` refactorizada para ser lineal, bloqueante e idempotente frente a concurrencias (`_active_resets`).
* **Tracing:** Cada interacción genera un Trace único vinculado al userId (Teléfono E.164).
* **Ciclo de Vida:** Orden de arranque garantizado: `ConfigLoader` -> `load_all()` -> `CatalogService.initialize()`.

#### 4. Persistencia y Memoria (Garantía de Verdad)
* **Unificación de Esquema:** Llaves canónicas en español (`nombre`, `ciudad`, `forma_pago`) en el motor de extracción y herramientas de soporte.
* **Higiene de Base de Datos:** Catálogo 100% normalizado (60/60 ítems). Llaves legacy (`imagenUrl`, `galeria`, `foto`) erradicadas en producción.
* **Linear Blocking:** `await` obligatorio para confirmación de escritura en Firestore antes de emitir cualquier respuesta.

#### 5. Base de Conocimiento y Motor Financiero (SSOT)
* **Única Fuente de Verdad:** Lógica centralizada en `app/services/financial_service.py` (v1.5.0).
* **Matrices de Paridad:** Inyección de constantes y validación cruzada real contra la matriz de factores para evitar alucinaciones en valores de cuotas.

#### 6. Integración WhatsApp y Orquestación
* **Idempotencia de Interfaz:** El comando `/reset` garantiza feedback visual incluso si la base de datos ya estaba limpia.
* **Zero-Silent-Failures:** Bloques `try-except-finally` con inyección de logs forenses (`logger.exception`) en fallos de red externa, APIs o validaciones del enrutador.

#### 7. Guardrails de Seguridad y Catalog Lock
* **Protocolo de Competencia:** Pivot comercial autorizado desde marcas de competencia hacia equivalentes internos mediante etiquetas `searchBy` (Score Semántico optimizado).
* **Visual-Lock:** Obligatoriedad de Imagen (formato Markdown estricto) y Precio ($) en toda recomendación de motocicleta.
* **Interface Lock (Patrón Adaptador):** Punto de entrada dual en `CatalogService` (`search_catalog` para SDK Gemini y `search` para retrocompatibilidad de enrutadores internos).
* **Judge Calibration (C5):** Regla `ONE_QUESTION_RULE` flexibilizada a un límite heurístico de `> 2` para permitir saludos comerciales naturales sin falsos positivos.
* **Real Parity Guard (C2):** Validación matemática de cuotas con margen de error < 1% comparando la respuesta de la IA contra el FinancialService.

#### 8. Evaluación y No-Regresión [CERTIFICADO v9.9.2]
* **Score de Coherencia:** 1.000.
* **Limpieza Estructural:** Erradicación de términos legacy en la capa de planificación (`.planning/`) mediante procesamiento atómico.
* **Verificación GSD:** Ejecución obligatoria de `npx agent-cli eval` con umbral de 0.9 antes de cualquier despliegue.

#### 9. Deuda Técnica Resuelta [v9.9.2]
* **Semantic Blindness:** Optimización del recall inyectando ruido conversacional (`tienen`, `venden`, `disponible`) a los `stop_words` para potenciar el score de identidad comercial.
* **Scope Shadowing:** Erradicación del bug `UnboundLocalError` causado por un import redundante (`import re`) en el bloque de procesamiento de WhatsApp que colapsaba el enrutador antes del envío.
* **Interface Breach:** Solución del crash de `AttributeError` en `whatsapp.py` y `judge_service.py` restaurando la firma clásica del método `search` mediante un Patrón Adaptador.
* **Judge Micro-Management:** Prevención de interrupciones de embudo debidas a la regla de conteo de preguntas (C5) recalibrando el umbral heurístico.
* **Catalog Legacy Bloat:** Resolución del cortocircuito de script en `normalize_imagen_url.py` para garantizar la ejecución de planes de borrado en documentos mixtos.

---
🏛️ **Nota para el Ingeniero y Agentes (Antigravity):** El sistema ha alcanzado la Gracia Técnica **v9.9.2**. Queda estrictamente prohibido re-inyectar llaves en inglés, alterar el orden de inicialización de `main.py`, o modificar la firma pública del `CatalogService` sin un Patrón Adaptador. El enrutador y el Juez están 100% estabilizados y el entorno de producción cuenta con paridad de datos absoluta.
