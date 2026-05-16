# Master Project Document - Bot-TiendaLasMotos (v9.9.3)

## Vision
Implementar y consolidar a "Juan Pablo" como un Agente Único de contacto directo en WhatsApp, eliminando por completo las latencias de triaje y delegación de estados. El sistema opera de manera integrada y reactiva en tiempo real sobre una única base de datos compartida (Colección: `prospectos`) con la plataforma web de administración (CRM Next.js).

## Core Value
El desacoplamiento orgánico y la persistencia lineal bloqueante aseguran que el motor de extracción de la IA y la gestión humana de los asesores comerciales coexistan pacíficamente sin colisiones de datos ni sobreescrituras sucias de cuotas financieras reales.

## Technical Context
* **Backend Core:** Python 3.13 / FastAPI / Gemini 2.5 Flash.
* **Persistencia:** Firestore AsyncClient (`prospectos` como colección central).
* **Observabilidad Forense:** Trazado de costos y latencias vinculado vía Langfuse SDK.
* **Frontend CRM:** React / Next.js (App Router) en paridad absoluta v8.3.1.

## Target Users
* **Usuarios de WhatsApp:** Reciben una atención comercial fluida, empática y blindada bajo el script estricto de Habeas Data.
* **Equipo de Ventas/Finanzas (CRM):** Visualizan en tiempo real los 8 datos del perfilamiento conforme la IA los extrae, con la capacidad exclusiva de actualizar el estatus de crédito final.
* **Desarrolladores:** Arquitectura modular desacoplada basada en la Ley de Gall.

## Project Phases & Roadmap

### Fase 1: Arquitectura de Agente Único y Embudo Progresivo (COMPLETED)
* Consolidación de Juan Pablo como único punto de contacto.
* Implementación de Frenos Cognitivos en `calculate_credit_score` para erradicar placeholders.
* Sincronización del Dashboard de Scoring y Estados en la UI.

### Fase 2: Tríada RAG y IA-as-a-Judge (COMPLETED)
* Integración de Langfuse con decoradores `@observe` para trazabilidad forense.
* Configuración del Juez de Fundamentación para auditar la calidad conversacional.
* Sincronización de personalidad y salida elegante parametrizada.

### Fase 3: Infraestructura Nativa Firebase y Sincronización Reactiva (IN PROGRESS)
* **Tarea 3.1 (COMPLETED):** Modelo de Datos Compartido y Bloqueo de Concurrencia en Backend mediante `_CRM_PROTECTED_FIELDS`.
* **Tarea 3.2 (PLANNED):** Reactividad en Tiempo Real vía `onSnapshot` en Next.js.
* **Tarea 3.3 (PLANNED):** Observabilidad de Transacciones y alertas de Timeouts de Firestore.

### Fase 4: Optimización de Costos y Seguridad / Red Teaming (PLANNED)
* Implementación de Caché Semántica con similitud coseno > 0.85.
* Pruebas de estrés adversarial contra Prompt Injection.
* Compresión de contexto y payload del catálogo inyectado.

---
*Última Certificación de Sincronía: 2026-05-15 (v9.9.3)*