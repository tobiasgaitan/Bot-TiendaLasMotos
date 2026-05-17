🛡️ Documento Maestro: Estado de Desarrollo Bot-TiendaLasMotos (v9.9.8)
Versión Actual: v9.9.8 (Resolución de Regresión en Herramientas, Control Explícito de Excepciones, Inicialización de Ámbito, Purga Topológica y Validación de Enmascaramiento Nulo).
Último Hito: Cierre de tickets BOT-PERF-46 y BOT-ARQ-46: Eliminación definitiva de la regresión de tool-calling en ai_brain.py mediante la migración interna de la herramienta search_catalog hacia el método estructurado search_items. Se erradicó el riesgo de UnboundLocalError, se blindó el flujo con validación Anti-Null Masking automatizada y se ejecutó la destrucción física del código fantasma (memory_service_v95.py, audit_finance_v140.py), sincronizando el árbol de dependencias estáticas.
Score de Coherencia: 1.000 (92/92 Tests PASSED) bajo Python 3.13.

1. Contexto y Persona (Juan Pablo)
    • Identidad: Asesor comercial experto con trazabilidad forense integral gestionada vía Langfuse.
    • Nomenclatura Técnica: Asociación obligatoria de datos capturados al esquema inmutable del sistema: moto_interest para registrar modelos y habeas_data_accepted para el estatus legal del lead.
    • Criterio de Verdad: Paridad v1.5.0 activa y constante de la directiva JUAN_PABLO_SYSTEM_INSTRUCTION sincronizada con la v9.9.5 de Firestore.
2. Stack Tecnológico y Dependencias
    • IA Core: Gemini 2.5 Flash (v2.0).
    • Algoritmo Semántico Local: difflib.SequenceMatcher nativo de la librería estándar de Python puro (sin dependencias externas pesadas), garantizando resoluciones de coincidencia tipográfica en microsegundos.
    • Observabilidad: Langfuse SDK con uso de decoradores @observe() para capturar latencia, costo de tokens y trazas de razonamiento.
    • Gestión: Orquestación y resolución de dependencias aisladas mediante el gestor uv.
3. Arquitectura de Infraestructura (GCP & Comandos)
    • Intercepción de Comandos: Lógica del comando interno /reset refactorizada para operar de manera lineal, bloqueante e idempotente frente a solicitudes concurrentes (_active_resets).
    • Tracing: Cada interacción del usuario genera un Trace de ejecución único vinculado a su identificador telefónico en formato canónico estricto E.164.
    • Ciclo de Vida: Orden de arranque del backend garantizado mediante la secuencia mandatoria: ConfigLoader -> load_all() -> CatalogService.initialize() -> _hydrate_cache().
4. Persistencia y Memoria (Garantía de Verdad)
    • Unificación de Esquema: Empleo estricto de llaves canónicas en español (nombre, ciudad, forma_pago) en el motor de extracción y herramientas.
    • Higiene de Base de Datos: Catálogo 100% normalizado (60/60 ítems devueltos). Llaves legacy erradicadas en producción.
    • Linear Blocking & Timeouts (BOT-INFRA-33): Uso obligatorio de await para la confirmación síncrona de escritura en Firestore. Adición del interceptor quirúrgico global _firestore_io mediante asyncio.wait_for parametrizado por la variable autovalidada settings.db_timeout (por defecto 5 segundos) protegiendo de forma síncrona los 9 métodos core de I/O de base de datos contra bloqueos y congelamiento.
    • Control de Concurrencia (Burst Mitigation): Aislamiento de la función update_whatsapp_status mediante un semáforo asíncrono (asyncio.Semaphore(5)) para prevenir la saturación del pool de sockets de red ante ráfagas de Meta.
    • Gobernanza de Datos Compartidos (BOT-INFRA-31): Blindaje atómico de la colección única prospectos contra sobreescrituras accidentales de la IA mediante la constante _CRM_PROTECTED_FIELDS. Los campos financieros manuales del asesor quedan aislados del motor de mezcla de extracción (_merge_extracted_data), permitiendo la coexistencia pacífica en tiempo real con el frontend Next.js.
5. Base de Conocimiento y Motor Financiero (SSOT)
    • Única Fuente de Verdad: Lógica financiera e inyección centralizada en el módulo app/services/financial_service.py (v1.5.0).
    • Matrices de Paridad: Inyección de constantes matemáticas y validación cruzada real contra la matriz de factores para erradicar la alucinación en cuotas.
6. Integración WhatsApp y Orquestación
    • Idempotencia de Interfaz: El comando /reset garantiza el envío de feedback visual inmediato incluso si la base de datos ya se encontraba limpia.
    • Zero-Silent-Failures & Contingency Dispatch (BOT-INFRA-33): Bloques try-except-finally con inyección mandatoria de logs forenses (logger.exception) en fallos de red externa o validaciones del enrutador. Ante un TimeoutError o excepciones nativas de la API de GCP, el interceptor ejecuta un despacho síncrono incondicional del mensaje de contingencia, anula dependencias circulares vía lazy import, y ejecuta un raise obligatorio para detener la ejecución y proteger el flujo.
7. Guardrails de Seguridad y Catalog Lock
    • Optimización por Caché Semántica (BOT-PERF-41): Intercepción quirúrgica in-memory en CatalogService.search_items. Si una consulta arroja un score fuzzy > 0.85 contra las llaves pre-calculadas, se aplica un Bypass inmediato del LLM, reduciendo un 100% el costo de tokens de red.
    • Hidratación Síncrona de Caché: Mitigación de cold-start mediante pre-calentamiento automatizado en el arranque, inyectando de forma síncrona los términos de búsqueda de mayor frecuencia comercial.
    • Preservación del Visual-Lock (PCC Pro): El almacenamiento y despacho desde la caché semántica local respeta estrictamente la inmutabilidad de formato impuesta por la REGLA_DE_VISUALES, garantizando que toda respuesta recupere obligatoriamente el precio y el enlace de la imagen estructurado en Markdown.
    • Protocolo de Competencia: Pivot comercial autorizado desde marcas de la competencia hacia equivalentes internos mediante etiquetas de coincidencia searchBy.
    • Judge Calibration (C5): Regla ONE_QUESTION_RULE flexibilizada a un límite heurístico de > 2 para permitir interacciones de saludo naturales.
    • Real Parity Guard (C2): Validación matemática de cuotas con un margen de error inferior al 1% comparando la respuesta del LLM contra el simulador financiero.
8. Evaluación y No-Regresión [CERTIFICADO v9.9.8]
    • Score de Coherencia de Regresión: 1.000 certificado de forma automatizada mediante la suite histórica ampliada (92/92 Tests PASSED), garantizando la estabilidad de la lógica de herramientas y la correcta propagación de errores.
    • Limpieza Estructural: Erradicación total de términos legacy en la capa de planificación del repositorio (.planning/) y destrucción del código fantasma en app/services/ (BOT-ARQ-46).
    • Verificación GSD: Ejecución obligatoria de evaluación (eval) con un umbral de aprobación estricto establecido en un mínimo de 0.9 antes de autorizar cualquier despliegue.
9. Deuda Técnica Resuelta [v9.9.8]
    • Tool Calling Alignment Failure (BOT-PERF-45): Se erradicó el fallo latente donde el orquestador invocaba search_catalog e intentaba procesar un diccionario buscando raw_price sobre lo que en realidad era un tipo string Markdown.
    • Ghost Code Eradication & AST Cleanup (BOT-ARQ-46): Purga física de los nodos huérfanos memory_service_v95.py y audit_finance_v140.py. Sincronización del índice graph.json eliminando falsos positivos topológicos y mitigando el riesgo crítico de Namespace Collision.
    • Null Masking on Critical Exceptions: Eliminación total de bloques except Exception as e tolerantes dentro del flujo de resolución de simulaciones financieras que ocultaban la desaparición de datos monetarios.
    • Network Token Inflation: Eliminación de llamadas a APIs externas para resolución vectorial de intenciones repetitivas.
    • Firestore Socket Starvation (BOT-INFRA-33): Contención de inundación de conexiones provocada por webhooks concurrentes de Meta.
    • CRM Data Overwrite Risk (BOT-INFRA-31): Guardrail quirúrgico en MemoryService que prohíbe a la IA pisar o degradar las cuotas financieras reales.
    • Tool Calling Regression & Scope Leak (BOT-PERF-46): Se eliminó de raíz la regresión que reinstalaba el string Markdown crudo de search_catalog. Se implementó un validador estricto que levanta un ValueError explícito ([NULL MASKING DETECTED]) si se detectan campos vacíos en llaves críticas antes de la serialización hacia el LLM. Se garantizó el Visual-Lock obligando la presencia explícita de la cadena "Ficha Tecnica:" mediante aserción automatizada (test_pcc_ficha_tecnica.py).
🏛️ Nota para el Ingeniero y Agentes (Antigravity): El sistema ha alcanzado la Gracia Técnica v9.9.8. Queda estrictamente prohibido re-inyectar llaves en inglés, alterar el orden de inicialización de main.py, o modificar las firmas de los diccionarios devueltos por search_items sin un Patrón Adaptador. Todas las protecciones de concurrencia, exclusión del CRM (_CRM_PROTECTED_FIELDS), interceptores de base de datos, validaciones de integridad de payloads y el protocolo anti-null masking de herramientas están 100% estabilizados y en paridad con la instancia Beta.
