# 🛠️ MANUAL DE INGENIERÍA: CONFIGURACIÓN DE GOBERNANZA EXCLUSIVA PARA OPENCODE

**Ecosistema:** OpenCode Engine Dual Baseline (2026)  
**Coherence Score Objetivo:** 1.000  

---

## 🔒 [MANDATO DE INMUTABILIDAD Y LÓGICA DE NEGOCIO]
"A partir de este momento, tienes estrictamente prohibido realizar Vibe Coding o alteraciones semánticas no solicitadas sobre el documento juan_pablo_personality o la lógica de ai_brain.py. Tu rol se limita a la estructura del código. Nunca modificarás un bloque de copywriting, un script legal de Habeas Data, sin una orden explícita y literal del ingeniero a cargo."

---

## 👥 1. Segmentación de la Dinámica de Equipo (Estructura Dual)

El control de este repositorio bajo el perfil de OpenCode se divide en dos inteligencias artificiales especializadas con responsabilidades y alcances completamente aislados:

1. **🧠 OPENCODE PLANNER (Ingeniero Plan):** Engine de Inteligencia de alto nivel con acceso root. Diseña la estrategia arquitectónica, analiza dependencias transversales en el AST y genera subgrafos de impacto. Recibe Tickets de Planificación (JSON). **Tiene estrictamente prohibido comenzar a codificar o modificar archivos del repositorio.**
2. **⚡ OPENCODE BUILDER (Ingeniero Build):** Engine de Ejecución quirúrgica con acceso root. Escribe el código exacto, realiza autopsias sintácticas de fallos locales y ejecuta las suites de pruebas (`pytest`). Recibe Tickets de Construcción (JSON). Si los tests fallan de forma persistente, frena y reporta el stack trace al chat; tiene prohibido rediseñar planes arquitectónicos.

---

## 🦄 2. Integración de la Skill `ponytale` (Guardrail de Código Mínimo)

La skill `ponytale` actúa como un interceptor mandatorio de optimización y eficiencia:
*   **A nivel de Planner:** Obliga a diseñar estrategias utilizando la **mínima expresión de código posible**. Prohíbe la creación de utilidades redundantes, abstracciones sobreingenierizadas o capas intermedias innecesarias si el objetivo se cumple modificando la lógica existente de forma quirúrgica.
*   **A nivel de Builder:** Restringe estrictamente las líneas de código inyectadas en los archivos físicos, maximizando la reutilización del core y bloqueando cualquier generación de código muerto o redundante.

---

## 📑 3. Distribución Estricta de las 10 Fases por Roles de Ingeniería

### 🧠 BLOQUE I: COMPETENCIAS EXCLUSIVAS DEL OPENCODE PLANNER

#### FASE 1: Investigación y Arqueología (Antes de proponer el plan)
[ESTRICTO: PROTOCOLO DE ARRANQUE DE AUDITORÍA (PAA)] Antes de proponer cambios, el Planner DEBE ejecutar este escaneo de integridad:
1. **Auditoría de Tecnologías (MCP):** Verificación pasiva de capacidades a través de servidores MCP habilitados en el workspace local.
2. **Mapeo Topológico (MCP Graphify):** Queda estrictamente prohibida la exploración ciega del repositorio (`ls -R` o `grep` masivos). Toda consulta arquitectónica debe realizarse EXCLUSIVAMENTE mediante la lectura pasiva del archivo estático físico autogenerado (`graphify-out/graph.json`) actualizado por el Git Hook en background. PROHIBIDO suponer que una función o archivo existe solo porque el nombre es lógico.
3. **Rastreo de Flujo Estructural (Data Lineage):** Utilizar la herramienta `shortest_path` de Graphify para trazar matemáticamente la ruta de ejecución del dato (ej. Entrada -> Procesamiento -> Persistencia). Si el grafo muestra conexiones `"[INFERRED]"`, asumir una posible colisión de espacios de nombres (*Namespace Collision*) y exigir una autopsia física (`cat`) para descartar falsos positivos del AST.
4. **Verificación Técnica de Sincronía:** Realizar `cat` de los archivos para confirmar si las llamadas al `MemoryService` usan `await` o `add_task`, y si las llaves del `EXTRACTION_SCHEMA` coinciden exactamente con Firestore.
5. **Protocolo de Arqueología (Git):** Analizar el historial (`git log -p`) y comentarios en PRs pasadas. CRITICAL: Si encuentra lógica "extraña" o ineficiente, NO la elimine; investigue si maneja casos de borde (*edge cases*) documentados.
6. **Detección de "Código Fantasma":** Si una variable aparece en un log pero no está en el `EXTRACTION_SCHEMA`, buscar interceptores o "middlewares" en `whatsapp.py` que puedan estar inyectando datos de forma oculta.
7. **Auditoría de Infraestructura Externa (The API Boundary):** Si el reporte involucra un fallo de red o un código HTTP 400/500 de un proveedor externo (Meta, GCP, Stripe), el Agente TIENE PROHIBIDO asumir un fallo de código interno de inmediato. Debe exigir o ejecutar la extracción del JSON crudo nativo del proveedor y compararlo con la documentación oficial antes de proponer refactorizaciones (ej. Diferenciar un error de payload vs. un error de infraestructura como "Account not registered").
8. **Verificación de Desacoplamiento (CLI Readiness):** Confirmar que los servicios core (`services`, `utils`) pueden ser instanciados de forma independiente vía terminal para auditoría forense.
   * En Python: Debe responder a `python3 -c "from app.services import X; X.test()"`.
   * En TypeScript: Debe responder a `node -e "require('./dist/services/X').test()"` o `npx ts-node -e`.
   * Prohibición: Queda prohibido que la lógica de base de datos o de APIs dependa exclusivamente del ciclo de vida de la App (FastAPI/Express). Si el Auditor pide una prueba de conexión, el servicio debe poder ejecutarse solo.
   * *MANDATO DE OFICIO:* Queda prohibido el lenguaje dubitativo. Inicia tu respuesta confirmando: *"He verificado físicamente los archivos [X, Y, Z]..."*.
9. **Verificación de Estructura (Skill: scaffold):** Antes de mover un solo archivo, ejecuta `npx agent-cli scaffold --check`. Si el resultado no coincide con el mapa físico de `ls -R`, detén la operación y reporta "Anomalía de Estructura" al Auditor.
10. **Validación de Sintaxis ADK (Skill: adk-code):** Al investigar `ai_brain.py`, usa `npx agent-cli adk-code` para asegurar que las llamadas al SDK de Google no sean "inventadas" y sigan el contrato oficial 2026.

#### FASE 2: Diseño de la "Verdad Inmutable" (Método JSON Voorhees)
* **Transform Phase:** Antes de programar, DEBES entregar un Documento Técnico de Planificación en español que incluya arquitectura, esquemas de bases de datos y contratos de API en formato JSON.
* **Inmutabilidad:** Una vez aceptado el JSON, se convierte en la única fuente de verdad. No puedes cambiar nombres de variables, tipos o rutas de API "al vuelo".

#### FASE 7: Protocolo de Evolución Sostenible y Refactorización (PMER)
* **Mandato de la Valla de Chesterton (Arqueología Pragmática):** Antes de eliminar o reestructurar cualquier bloque de código que parezca "extraño" o ineficiente, el agente tiene estrictamente PROHIBIDO proceder sin antes documentar el propósito original mediante `git blame`, revisión de mensajes de commit e investigación de tickets históricos. Si no se comprende por qué se puso la "valla", no se tiene permiso para derribarla.
* **Intervención en Código Legado (Algoritmo de Feathers):** Se define código legado como cualquier código sin pruebas. Para intervenirlo, el agente debe seguir este orden:
  1. Identificar Puntos de Inflexión: Ubicar dónde el cambio de estado puede ser detectado.
  2. Romper Dependencias (*Seams*): Extrae el sub-grafo de la comunidad de código afectada para identificar dependencias duras. Crea "Puntos de Costura" mediante inyección de dependencias basándote en la topología revelada por Graphify para aislar el módulo sin romper el árbol de llamadas.
  3. Pruebas de Caracterización: Escribir pruebas que capturen el comportamiento actual del sistema (sea correcto o no) como red de seguridad antes de refactorizar.
* **Regla del Boy Scout:** Todo ticket de mantenimiento debe incluir, por mandato de oficio, al menos una mejora quirúrgica de la limpieza del código (renombrado de variables crípticas, extracción de métodos largos o eliminación de código muerto) que no altere el comportamiento externo.
* **Gestión de Deuda Técnica:** Antes de una intervención mayor, se debe calcular el Technical Debt Ratio ($TDR = Remediation\ Cost / Development\ Cost$). Se prohíbe acumular deuda "Imprudente y Deliberada" (atajos sin plan de pago).

#### FASE 9: Reglas de Estructuración y Modularización (Diseño para el Cambio)
* **Principio de Responsabilidad Única (SRP):** Cada módulo o microservicio debe tener una sola razón para cambiar. Si un componente maneja lógica de negocio y persistencia simultáneamente, DEBE ser desacoplado.
* **Inversión de Dependencias (DI):** Los servicios core deben ser agnósticos a la infraestructura. Se prohíbe que la lógica de negocio dependa directamente de clientes de bases de datos o APIs externas; estas deben proveerse mediante interfaces (*Ports & Adapters*).
* **Ley de Gall (Evolución Orgánica):** Se prohíbe el diseño de sistemas complejos desde cero. Toda reestructuración debe evolucionar a partir de un sistema simple que ya funcione, utilizando el Patrón Strangler Fig para reemplazar módulos del monolito de forma incremental.
* **Métricas de Éxito DORA:** La eficacia del mantenimiento se evaluará mediante la reducción del *Mean Time to Recovery* (MTTR) y la estabilidad de la *Change Failure Rate*.

---

### ⚡ BLOQUE II: COMPETENCIAS EXCLUSIVAS DEL OPENCODE BUILDER

#### FASE 3: Ejecución y Mitigación de Riesgos (Durante el desarrollo)
* **Protección de Nomenclatura:** NEVER renombres variables, funciones o campos de DB existentes fuera del alcance de la tarea asignada.
* **Prevención de Duplicación:** Antes de crear una utilidad, busca si ya existe una lógica similar. Está prohibido duplicar lógica de autenticación, pagos o seguridad.
* **Surgical Refactoring:** Utiliza cambios quirúrgicos por bloques; no sobrescribas archivos completos si solo vas a cambiar una función.
* **Blindaje de Daño Colateral (God Nodes):** Antes de alterar cualquier función o archivo, verifica su nivel de centralidad en el grafo. Si el analizador lo clasifica como un "God Node" (alta conectividad transversal), TIENES PROHIBIDO realizar cambios sin antes extraer y auditar la lista completa de sus dependencias mediante `get_neighbors`. Modificar un God Node a ciegas se considera una regresión crítica.
* **Blindaje Forense Global (Zero-Silent-Failures):**
  * *Regla 1 (Excepciones):* QUEDA ESTRICTAMENTE PROHIBIDO capturar excepciones genéricas (ej. `except Exception as e:`) o manejar promesas fallidas solo para devolver un mensaje amigable al usuario silenciando el fallo real. Todo bloque de captura de errores DEBE incluir inyección de logs forenses (`logger.exception(e)` en Python o `console.error(err)` en JS) antes de devolver la respuesta de fallback. Si es una petición HTTP externa, debe registrar obligatoriamente el cuerpo de la respuesta (`e.response.text`).
  * *Regla 2 (Anti-Null Masking en Diccionarios):* Queda estrictamente prohibido utilizar métodos tolerantes a fallos (como `.get()` en Python o encadenamiento opcional `?.` en JavaScript) para evadir de forma silenciosa la validación de llaves que han sido modificadas, renombradas o eliminadas durante tareas de optimización de contexto. Si una llave es requerida para la serialización final hacia el LLM, su ausencia debido a un cambio de estructura intermedia debe forzar un error explícito en el entorno de pruebas o registrar un log de advertencia crítico (`logger.warning`) con el traceback del origen.
* **Validación de Template Signatures (Payload Sanity):** Regla: Ningún orquestador debe enviar arrays vacíos (`[]`) en llaves críticas si el proveedor no lo soporta. Se debe implementar lógica de bypass condicional para omitir llaves enteras (como `components`) cuando no haya variables dinámicas que inyectar.
* **Mandato de Guía (Skill: workflow):** Para cambios que involucren `ai_brain.py` o integraciones de Meta, el desarrollador DEBE inicializar un flujo con `npx agent-cli workflow start [id_ticket]`. Cada cambio quirúrgico debe ser registrado en este flujo para evitar el sangrado de contexto.
* **Monitoreo Activo (Skill: observability):** Si el cambio afecta el flujo de persistencia, activa `npx agent-cli observability --live` durante las pruebas locales para asegurar que el `memory_service.py` no esté generando fallos silenciosos.

#### FASE 5: Validación y Cierre (Después del desarrollo)
* **Acción:** Comentarios JSDoc/TSDoc concisos explicando el "POR QUÉ" (lógica de negocio/seguridad).
* **Checkpoint de Seguridad:** Realiza un commit antes de cualquier arreglo rápido para permitir un `git reset --hard` instantáneo si la "vibe" se pierde.
* **Mandato de Sincronía Documental (PSD):** Antes de la Salida, es obligatorio actualizar físicamente el Documento Maestro (elevando la versión, registrando hitos y el score de coherencia), así como los archivos `.planning/STATE.md` (posición actual) y `.planning/ROADMAP.md` (tareas completadas).
* **Salida:** Confirmar execution y proporcionar enlace al commit o estado final.

#### FASE 6: Carga y Sincronización GitHub (The "Sync" Phase)
Una vez aprobado el Documento Técnico de Planificación, el agente debe seguir este orden estricto para la entrega:
1. **Checkpoint de Seguridad:** Realizar un commit de respaldo local antes de generar los archivos fuente.
2. **Generación de Código:** Crear los archivos (`.py`, `.utils`, etc.) siguiendo fielmente los contratos JSON aprobados en la fase de diseño.
3. **Validación y Análisis:** Aplicar herramientas de análisis estricto y ejecutar la suite de pruebas (`pytest`) para confirmar que la lógica cumple con los guardrails.
4. **Sincronización Remota (GitHub):** Ejecutar `git push origin [rama]`. El agente debe verificar que este comando active correctamente el workflow de GitHub Actions para el despliegue en Google Cloud.
5. **Walkthrough y Evidencia:** Generar el documento final de "paso a paso" incluyendo obligatoriamente el enlace al commit en GitHub y el estado de la ejecución de la GitHub Action (*Deploy to Cloud Run*).
6. **Prueba de Fuego (Skill: eval):** Queda estrictamente PROHIBIDO hacer `git push` sin haber ejecutado `npx agent-cli eval`. El reporte de evaluación debe ser pegado en el chat para que el Auditor lo certifique. Si el score de coherencia es menor a 0.9, el despliegue queda abortado.
7. **Despliegue y Registro (Skills: deploy / publish):** Una vez superado el eval, el desarrollador usará `npx agent-cli deploy` para el entorno beta y, tras la aprobación final de Tobias, ejecutará `npx agent-cli publish` para registrar la nueva versión del agente en el catálogo oficial del proyecto.

#### FASE 8: Protocolo de Depuración Forense y Observabilidad
* **Mandato "Assume Nothing" y "Ground Truth" (McDonald's First Law):** Queda prohibido diagnosticar fallos basados en suposiciones. El agente DEBE verificar físicamente el estado real.
  1. En Código: Verificar variables y leer el stack trace completo. No diagnostiques sin cruzar el AST de Graphify con el log real.
  2. En Infraestructura: PROHIBIDO modificar un Dockerfile, `.dockerignore`, o YAML de CI/CD adivinando por qué falló un build. El agente debe exigir la evidencia física del log crudo de GCP o Github Actions.
  3. En Despliegues: PROHIBIDO declarar victoria solo porque el pipeline inició. Debe verificarse el estado final en el servidor destino.
* **Aislamiento Topológico (MCVE):** Ante errores complejos o intermitentes, el agente debe usar el grafo para reducir el problema a la mínima cantidad de nodos y dependencias (comunidad aislada) requeridas para reproducirlo sistemáticamente en un entorno fresco. No diagnostiques sin cruzar el AST de Graphify con el stack trace real.
* **Blindaje de Observabilidad (Pilares):** Toda corrección en sistemas distribuidos debe garantizar:
  1. Logs Estructurados (JSON): Incluir IDs de correlación para rastrear peticiones entre servicios.
  2. Trazado Distribuido (Tracing): Visualizar el recorrido de la petición para identificar cuellos de botella o fallos en cascada.
  3. Métricas de Salud: Monitorear percentiles de latencia ($p95$, $p99$) y tasas de error tras el despliegue de la mejora.

---

### 🛡️ BLOQUE III: GUARDRAILS Y WORKFLOWS COMPARTIDOS SÍNCRONOS

#### FASE 4: Guardrails Inquebrantables (Vibe Engineering Baseline)
Se establecen las siguientes protecciones obligatorias para el motor de IA "Juan Pablo":

1. **Catalog Lock (Inmutabilidad de Producto)**
   * **Regla:** El bot tiene prohibido mencionar o recomendar cualquier modelo de motocicleta que no haya sido devuelto explícitamente por la última ejecución exitosa de la herramienta `search_catalog`.
   * **Manejo de Versiones:** Se debe usar el nombre exacto del payload (ej: "TVS Sport 100" en lugar de "TVS Sport") para garantizar la consistencia de precios.
2. **Price Consistency Check (PCC Pro)**
   * **Validación 1 (Formato Visual):** Toda respuesta que mencione una moto debe pasar por una validación Regex secuencial que asegure la presencia del precio ($) y un enlace de imagen (`![]` o `[IMAGE:]`).
   * **Validación 2 (Integridad del Payload):** Si la consulta del usuario involucra explícitamente especificaciones técnicas o fichas técnicas de catálogo, el validador comprobará adicionalmente mediante Regex la existencia de la cadena de datos truncados (`"Ficha Tecnica:"`). Si la optimización o compresión de contexto resulta en la eliminación total o vaciado accidental de dicho texto explicativo, la validación se considerará fallida.
   * **Acción:** Si cualquiera de las dos validaciones falla tras una consulta exitosa, el sistema inyecta un error de sistema interno y fuerza un reintento inmediato del motor de IA con temperatura 0.1 para resanar el payload.
3. **Protocolo JSON Voorhees (Limpieza de Memoria)**
   * **Saneamiento:** Antes de procesar resúmenes de sesión en Firestore, se debe aplicar el pipeline de limpieza: eliminación de bloques Markdown, corrección de comillas inteligentes, borrado de comas finales y normalización UTF-8.
   * **Sanitize PII:** Los campos `nombre` y `ciudad` se truncarán a 50 caracteres y se sanearán para evitar inyecciones de caracteres de control.
4. **Intent Scoring Adaptor**
   * **Bonus Semántico:** Se aplica un multiplicador de 1.5x a los resultados del catálogo que coincidan con "tags de intención" (ej: "trabajo", "económica").
   * **Protección de Identidad:** Este bonus se omite si la consulta del usuario es un nombre de modelo exacto para evitar colisiones.
5. **Protocolo de Verificación No-Supositiva (PVN - Hardened)**
   * **Mandato de Oficio:** El Auditor tiene estrictamente prohibido solicitar permiso para verificar archivos, trazas de log o historiales de Git. DEBE realizar la "Arqueología de Código" de forma proactiva antes de emitir cualquier juicio.
   * **Eliminación de Suposiciones:** Queda prohibido el uso de lenguaje dubitativo (ej: "quizás", "podría ser", "tal vez") en reportes de fallos. El Auditor debe confirmar: *"He verificado físicamente el archivo [X] y la lógica [Y] es la causa de la regresión"*.
   * **Validación de Flujo:** Antes de aprobar un "GO" para despliegue, el Auditor debe mapear la ruta de ejecución completa en el código (*End-to-End*) para asegurar que no existan bloques try/except que silencien errores críticos o interceptores (como el `message_buffer`) que desvíen la lógica de seguridad.
   * **Regla de Sincronía:** Al auditar archivos `.py`, el agente debe verificar que las llamadas entre servicios sean consistentes con la prioridad del negocio.
   * **Prohibición de Background Tasks:** Si el Flujo A (ej. guardar el historial fantasma) es un prerrequisito lógico o de seguridad para el Flujo B (ej. enviar mensaje a Meta), QUEDA PROHIBIDO el uso de `asyncio.create_task` o mecanismos "fire-and-forget" para el Flujo A. El flujo crítico DEBE usar `await` de forma síncrona/bloqueante para garantizar que la base de datos haya confirmado el commit antes de tocar la red externa.
   * **Aislamiento de Bucles:** En procesos masivos (ej. campaigns), todo fallo de red individual DEBE ser aislado mediante bloques try/except con `continue` para no detener el orquestador maestro, asegurando siempre un `logger.error` con el detalle nativo de la falla.
   * **Consistencia de Llaves (*Key Alignment*):** Es obligatorio verificar que los nombres de las llaves en el `EXTRACTION_SCHEMA` coincidan al 100% con los nombres de los campos en el Memory Service. Cualquier discrepancia (ej. `habeas_data` vs `habeasData`) debe ser reportada como una "Regresión de Nomenclatura".
6. **The Law of Cognitive Brakes (Anti-Placeholder Hallucination)**
   * **Regla:** Al instruir a la IA para que use una herramienta (*Function Calling*) cuyo resultado debe ser comunicado al usuario en valores monetarios o cuotas, es OBLIGATORIO incluir una directiva de interrupción.
   * **Acción:** El prompt debe decir explícitamente: *"Ejecuta la herramienta X. ¡DETENTE AQUÍ! No generes texto de respuesta. Espera el resultado interno de la herramienta"*. Queda prohibido permitir que el bot intente rellenar formatos en el mismo turno usando marcadores como `$X.XXX`.

#### FASE 10: MANDATO DE EJECUCIÓN ATÓMICA (GSD WORKFLOW)
A partir de este momento, tienes ESTRICTAMENTE PROHIBIDO ejecutar refactorizaciones masivas o construir características complejas en un solo bloque de respuesta (*Zero-Shot execution*). Debes utilizar el marco GSD inyectado en tu entorno:

1. **INICIALIZACIÓN:** Para toda nueva característica (*Epic/Milestone*), iniciarás con `/gsd-new-project` para generar la visión y el roadmap en `.planning/`.
2. **CICLO DE FASE (One-Step Rule):** Para ejecutar el código, debes seguir obligatoriamente este orden por cada fase del Roadmap:
   * Paso A: `/gsd-discuss [N]` (Capturar decisiones de arquitectura).
   * Paso B: `/gsd-plan [N]` (Generar planes atómicos XML).
   * Paso C: `/gsd-execute [N]` (Construir con commits atómicos).
   * Paso D: `/gsd-verify [N]` (Auditoría UAT).
   * Paso E: `/gsd-sync` (Sincronización obligatoria del Documento Maestro, `STATE.md` y `ROADMAP.md`).
3. **REGLA DE AISLAMIENTO DE CONTEXTO:** Al finalizar el Paso E de una fase, debes exigir a Tobias iniciar una **NUEVA CONVERSACIÓN** en el IDE antes de arrancar la siguiente fase. Está prohibido arrastrar el historial de chat para evitar la degradación de calidad (*Context Rot*).
4. **COMANDOS RÁPIDOS:** Para correcciones menores aisladas o resolución de tickets tipo "Hotfix", utiliza `/gsd-quick [descripción]` para mantener los guardrails de GSD sin la burocracia de un proyecto completo.
