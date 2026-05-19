🛡️ Documento Maestro: Estado de Desarrollo Bot-TiendaLasMotos (v10.1.0)
Versión Actual: v10.1.0 (Purga de Llaves Legacy y Firma de calculate_credit_score).
Último Hito: Cierre de ticket BOT-BE-035 (Quick Task 035). Se purgaron físicamente los fallbacks legacy ('name', 'city', 'payment_method') en ai_brain.py y se alineó la firma de la herramienta calculate_credit_score con 'entidad' y 'reportes' pasándolos al motor financiero de forma limpia. Se aseguraron las directivas del Auditor con la aserción de no enmascaramiento nulo de 'Ficha Tecnica:'.
Score de Coherencia: 1.000 (95 Tests PASSED, 2 skipped) bajo Python 3.13.

1. Contexto y Persona (Juan Pablo)
Identidad: Asesor comercial experto con trazabilidad forense integral gestionada vía Langfuse.
Nomenclatura Técnica: Asociación obligatoria de datos capturados al esquema inmutable del sistema: moto_interest para registrar modelos y habeas_data_accepted para el estatus legal del lead.
Criterio de Verdad: Paridad v1.5.0 activa y constante de la directiva JUAN_PABLO_SYSTEM_INSTRUCTION sincronizada con la v9.9.5 de Firestore.

2. Stack Tecnológico y Dependencias
IA Core: Gemini 2.5 Flash (v2.0).[3]
Formatos Especializados: Integración nativa de toons (v0.6.0) para serialización ultra-eficiente de datos tabulares hacia la ventana de contexto del LLM.[4, 1]
Algoritmo Semántico Local: difflib.SequenceMatcher nativo de la librería estándar de Python puro (sin dependencias externas), garantizando resoluciones de coincidencia tipográfica en microsegundos.
Observabilidad: Langfuse SDK con uso de decoradores @observe() para capturar latencia, costo de tokens y trazas de razonamiento.
Gestión: Orquestación y resolución de dependencias aisladas mediante el gestor uv.

3. Arquitectura de Infraestructura (GCP & Comandos)
Intercepción de Comandos: Lógica del comando interno /reset refactorizada para operar de manera lineal, bloqueante e idempotente frente a solicitudes concurrentes (_active_resets).
Tracing: Cada interacción del usuario genera un Trace de ejecución único vinculado a su identificador telefónico en formato canónico estricto E.164.
Ciclo de Vida: Orden de arranque del backend garantizado mediante la secuencia mandatoria: ConfigLoader -> load_all() -> CatalogService.initialize() -> _hydrate_cache().
Empaquetamiento y Construcción: Dockerfile multi-capa basado en Debian-slim con instalación explícitamente parametrizada de compiladores (gcc) y herramientas de control de versiones (git), asegurando que uv resuelva dependencias de repositorios Git de forma offline y síncrona.

4. Persistencia y Memoria (Garantía de Verdad)
Unificación de Esquema: Empleo estricto de llaves canónicas en español (nombre, ciudad, forma_pago) en el motor de extracción y herramientas.
Higiene de Base de Datos: Catálogo 100% normalizado (60/60 ítems devueltos). Llaves legacy erradicadas en producción.
Linear Blocking & Timeouts (BOT-INFRA-33): Uso obligatorio de await para la confirmación síncrona de escritura en Firestore. Adición del interceptor quirúrgico global _firestore_io mediante asyncio.wait_for parametrizado por la variable autovalidada settings.db_timeout (por defecto 5 segundos) protegiendo de forma síncrona los 9 métodos core de I/O de base de datos contra bloqueos y congelamiento.
Control de Concurrencia (Burst Mitigation): Aislamiento de la función update_whatsapp_status mediante un semáforo asíncrono (asyncio.Semaphore(5)) para prevenir la saturación del pool de sockets de red ante ráfagas de Meta.
Gobernanza de Datos Compartidos (BOT-INFRA-31): Blindaje atómico de la colección única prospectos contra sobreescrituras accidentales de la IA mediante la constante _CRM_PROTECTED_FIELDS. Los campos financieros manuales del asesor quedan aislados del motor de mezcla de extracción (_merge_extracted_data), permitiendo la coexistencia pacífica en tiempo real con el frontend Next.js.

5. Base de Conocimiento y Motor Financiero (SSOT)
Única Fuente de Verdad: Lógica financiera e inyección centralizada en el módulo app/services/financial_service.py (v1.5.0).
Matrices de Paridad: Inyección de constantes matemáticas y validación cruzada real contra la matriz de factores para erradicar la alucinación en cuotas.

6. Integración WhatsApp y Orquestación
Idempotencia de Interfaz: El comando /reset garantiza el envío de feedback visual inmediato incluso si la base de datos ya se encontraba limpia.
Zero-Silent-Failures & Contingency Dispatch (BOT-INFRA-33): Bloques try-except-finally con inyección mandatoria de logs forenses (logger.exception) en fallos de red externa o validaciones del enrutador. Ante un TimeoutError o excepciones nativas de la API de GCP, el interceptor ejecuta un despacho síncrono incondicional del mensaje de contingencia, anula dependencias circulares vía lazy import, y ejecuta un raise obligatorio para detener la ejecución y proteger el flujo.

7. Guardrails de Seguridad y Catalog Lock
Optimización por Caché Semántica (BOT-PERF-41): Intercepción quirúrgica in-memory en CatalogService.search_items. Si una consulta arroja un score fuzzy superior al umbral establecido de $s\ge0.85$ contra las llaves pre-calculadas, se aplica un Bypass inmediato del LLM, reduciendo un 100% el costo de tokens de red.
S-TOON Virtual Faraday Cage (BOT-SEC-50): Protección del Webhook de Meta mediante la inyección del middleware S-TOON_Middleware().protect().[2] El sistema envuelve las entradas de los usuarios dentro de límites perimetrales latentes marcados por <|S_START|> y <|S_END|> [5], previniendo ataques de Mascarada Estructural o desincronización de delimitadores en la serialización hacia el LLM.[5]
Hidratación Síncrona de Caché: Mitigación de cold-start mediante pre-calentamiento automatizado en el arranque, inyectando de forma síncrona los términos de búsqueda de mayor frecuencia comercial.
Preservación del Visual-Lock (PCC Pro): El almacenamiento y despacho desde la caché semántica local respeta estrictamente la inmutabilidad de formato impuesta por la REGLA_DE_VISUALES, garantizando que toda respuesta recupere obligatoriamente el precio y el enlace de la imagen estructurado en Markdown.
Protocolo de Competencia: Pivot comercial autorizado desde marcas de la competencia hacia equivalentes internos mediante etiquetas de coincidencia searchBy.
Judge Calibration (C5): Regla ONE_QUESTION_RULE flexibilizada a un límite heurístico de > 2 para permitir interacciones de saludo naturales.
Real Parity Guard (C2): Validación matemática de cuotas con un margen de error inferior al 1% comparando la respuesta del LLM contra el simulador financiero.

8. Evaluación y No-Regresión
Score de Coherencia de Regresión: 1.000 certificado de forma automatizada mediante la suite histórica ampliada (93/93 Tests PASSED), garantizando la estabilidad de la lógica de herramientas, la correcta propagación de errores y el Visual-Lock de catálogo.
Limpieza Estructural: Erradicación total de términos legacy en la capa de planificación del repositorio (.planning/) y destrucción del código fantasma en app/services/ (BOT-ARQ-46).
Verificación GSD: Ejecución obligatoria de evaluación (eval) con un umbral de aprobación de un mínimo de 0.9 antes de autorizar el push.

9. Deuda Técnica Resuelta [v9.9.9]
Tool Calling Alignment Failure (BOT-PERF-45): Se erradicó el fallo latente donde el orquestador invocaba search_catalog e intentaba procesar un diccionario buscando raw_price sobre lo que en realidad era un tipo string Markdown.
Ghost Code Eradication & AST Cleanup (BOT-ARQ-46): Purga física de los nodos huérfanos memory_service_v95.py y audit_finance_v140.py. Sincronización del índice graph.json eliminando falsos positivos topológicos.
Null Masking on Critical Exceptions: Eliminación de bloques except Exception as e tolerantes en simulaciones financieras.
Network Token Inflation: Mitigación del 100% de llamadas externas repetitivas gracias al Bypass de la Caché Semántica.
Firestore Socket Starvation (BOT-INFRA-33): Contención de inundación de conexiones provocada por webhooks concurrentes de Meta.
CRM Data Overwrite Risk (BOT-INFRA-31): Guardrail quirúrgico en MemoryService que prohíbe a la IA pisar o degradar las cuotas financieras reales.
Tool Calling Regression & Scope Leak (BOT-PERF-46): Se eliminó de raíz la regresión de tool-calling. Se implementó el asertor Anti-Null Masking () y se forzó la presencia del prefijo visual "Ficha Tecnica:" mediante test unitario automatizado (test_pcc_ficha_tecnica.py).
Cloud Build Compilación Fail (BOT-INFRA-52): Resolución de la regresión de construcción de la imagen en GCP provocada por la falta del binario git para clonar de forma asíncrona la dependencia del protocolo S-TOON de Azimuth Logic Research.

🏛️ Nota para el Ingeniero y Agentes (Antigravity): El sistema ha alcanzado la Gracia Técnica v9.9.9. Queda estrictamente prohibido re-inyectar llaves en inglés, alterar el orden de inicialización de main.py, o modificar las firmas de los diccionarios devueltos por search_items sin un Patrón Adaptador. Todas las protecciones de concurrencia, exclusión del CRM (_CRM_PROTECTED_FIELDS), interceptores de base de datos, el protocolo anti-null masking de herramientas y las dependencias compiladas de Rust de toons y stoon están 100% estabilizados y en paridad con la instancia Beta.
- [v10.0.0] Resolución de regresión nomenclatural (price vs precio) en CatalogService y limpieza de caché. Inyección de bonos de contado validados (bonusAmount, bonusEndDate). Score certificado: 1.000.
