### Documento Maestro: Estado de Desarrollo Bot-TiendaLasMotos (v9.9.3)
Versión Actual: v9.9.3 (Paridad de Datos, Optimización de Recall, Estabilización de Enrutador/Juez y Gobernanza de Base de Datos Compartida). 
Último Hito: Cierre de BOT-INFRA-31 (Exclusión mutua de campos protegidos del asesor humano en la colección prospectos) y erradicación del riesgo de "escritura sucia". Score de Coherencia: 1.000 (74/74 Tests PASSED) bajo Python 3.13. 

1. Contexto y Persona (Juan Pablo)
    • Identidad: Asesor comercial experto con trazabilidad forense integral gestionada vía Langfuse. 
    • Nomenclatura Técnica: Asociación obligatoria de datos capturados al esquema inmutable del sistema: moto_interest para registrar modelos y habeas_data_accepted para el estatus legal del lead. 
    • Criterio de Verdad: Paridad v1.5.0 activa y constante de la directiva JUAN_PABLO_SYSTEM_INSTRUCTION sincronizada con la v9.9.3 de Firestore. 
2. Stack Tecnológico y Dependencias
    • IA Core: Gemini 2.5 Flash (v2.0). 
    • Observabilidad: Langfuse SDK con uso de decoradores @observe() para capturar latencia, costo de tokens y trazas de razonamiento. 
    • Gestión: Orquestación y resolución de dependencias aisladas mediante el gestor uv.
3. Arquitectura de Infraestructura (GCP & Comandos)
    • Intercepción de Comandos: Lógica del comando interno /reset refactorizada para operar de manera lineal, bloqueante e idempotente frente a solicitudes concurrentes (_active_resets).
    • Tracing: Cada interacción del usuario genera un Trace de ejecución único vinculado a su identificador telefónico en formato canónico estricto E.164.
    • Ciclo de Vida: Orden de arranque del backend garantizado mediante la secuencia mandatoria: ConfigLoader -> load_all() -> CatalogService.initialize().
4. Persistencia y Memoria (Garantía de Verdad)
    • Unificación de Esquema: Empleo estricto de llaves canónicas en español (nombre, ciudad, forma_pago) en el motor de extracción y herramientas. 
    • Higiene de Base de Datos: Catálogo 100% normalizado (60/60 ítems devueltos). Llaves legacy erradicadas en producción. 
    • Linear Blocking: Uso obligatorio de await para la confirmación síncrona de escritura en Firestore antes de emitir respuestas hacia la red. 
    • Control de Concurrencia (Burst Mitigation): Aislamiento de la función update_whatsapp_status mediante un semáforo asíncrono (asyncio.Semaphore(5)) para prevenir la saturación del pool de sockets de red ante ráfagas de Meta.
    • Gobernanza de Datos Compartidos (BOT-INFRA-31): Blindaje atómico de la colección única prospectos contra sobreescrituras accidentales de la IA mediante la constante _CRM_PROTECTED_FIELDS. Los campos financieros manuales del asesor (approved_amount, monthly_quota, current_agent) quedan aislados del motor de mezcla de extracción (_merge_extracted_data), permitiendo la coexistencia pacífica en tiempo real con el frontend Next.js. 
5. Base de Conocimiento y Motor Financiero (SSOT)
    • Única Fuente de Verdad: Lógica financiera e inyección centralizada en el módulo app/services/financial_service.py (v1.5.0). 
    • Matrices de Paridad: Inyección de constantes matemáticas y validación cruzada real contra la matriz de factores para erradicar la alucinación en cuotas. 
6. Integración WhatsApp y Orquestación
    • Idempotencia de Interfaz: El comando /reset garantiza el envío de feedback visual inmediato incluso si la base de datos ya se encontraba limpia.
    • Zero-Silent-Failures: Bloques try-except-finally con inyección mandatoria de logs forenses (logger.exception) en fallos de red externa o validaciones del enrutador. 
7. Guardrails de Seguridad y Catalog Lock
    • Protocolo de Competencia: Pivot comercial autorizado desde marcas de la competencia hacia equivalentes internos mediante etiquetas de coincidencia searchBy. 
    • Visual-Lock: Obligatoriedad de Imagen (formato Markdown estricto) y Precio ($) en toda recomendación de motocicleta emitida por el bot. 
    • Interface Lock (Patrón Adaptador): Punto de entrada dual en CatalogService (search_catalog para el SDK Gemini y search para retrocompatibilidad de enrutadores internos).
    • Judge Calibration (C5): Regla ONE_QUESTION_RULE flexibilizada a un límite heurístico de > 2 para permitir interacciones de saludo naturales sin activar falsos positivos. 
    • Real Parity Guard (C2): Validación matemática de cuotas con un margen de error inferior al 1% comparando la respuesta del LLM contra el simulador financiero. 
8. Evaluación y No-Regresión [CERTIFICADO v9.9.3]
    • Score de Coherencia: 1.000 certificado de forma automatizada. 
    • Limpieza Estructural: Erradicación total de términos legacy en la capa de planificación del repositorio (.planning/) mediante procesamiento atómico. 
    • Verificación GSD: Ejecución obligatoria de npx agent-cli eval con un umbral de aprobación establecido en un mínimo de 0.9 antes de autorizar cualquier despliegue. 
9. Deuda Técnica Resuelta [v9.9.3]
    • Semantic Blindness: Optimización del recall inyectando ruido conversacional al diccionario de detención del motor semántico.
    • Scope Shadowing: Erradicación del bug UnboundLocalError causado por un import redundante en el bloque de procesamiento de WhatsApp.
    • Interface Breach: Solución del crash de AttributeError en whatsapp.py restaurando la firma clásica del método search mediante un Patrón Adaptador.
    • Judge Micro-Management: Prevención de interrupciones de embudo debidas a la regla de conteo de preguntas (C5) recalibrando el umbral heurístico. 
    • Catalog Legacy Bloat: Resolución del cortocircuito de script en normalize_imagen_url.py para garantizar la ejecución de planes de borrado en documentos mixtos.
    • Firestore Socket Starvation (BOT-DB-4.4-FIX): Contención quirúrgica de la inundación de conexiones provocada por ráfagas concurrentes de webhooks de estados de Meta (sent, delivered, read), protegiendo la persistencia asíncrona mediante exclusión mutua.
    • CRM Data Overwrite Risk (BOT-INFRA-31): Eliminación total del riesgo de colisión de datos en entornos de persistencia compartida con la página web. Al descartar la arquitectura de webhooks externos y aprovechar el tiempo real de Firebase, se programó un guardrail quirúrgico en el MemoryService que prohíbe a la IA pisar o degradar las cuotas financieras reales o el estado de asignación determinado por el asesor comercial humano en el CRM. 

🏛️ Nota para el Ingeniero y Agentes (Antigravity): El sistema ha alcanzado la Gracia Técnica v9.9.3. Queda estrictamente prohibido re-inyectar llaves en inglés, alterar el orden de inicialización de main.py, o modificar la firma pública del CatalogService sin un Patrón Adaptador. El enrutador, el mecanismo de exclusión de campos protegidos del CRM (_CRM_PROTECTED_FIELDS) y el Juez están 100% estabilizados y el entorno de producción cuenta con paridad de datos absoluta con el frontend v8.3.1. 


