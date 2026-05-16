# Functional & Technical Requirements - Bot-TiendaLasMotos

## Overview
Requisitos arquitectónicos para la consolidación del Agente Único "Juan Pablo" y su sincronización reactiva nativa con la base de datos de Firebase compartida con la página web.

## Architecture Core Requirements

### Phase 1: Agente Único y Control Cognitivo (Consolidado)
* **R1 - Single Point of Contact:** Erradicar cualquier flujo de triaje. Juan Pablo gestiona de forma directa y lineal todo el ciclo del lead.
* **R2 - Canonical Keys:** Persistencia obligatoria de `moto_interest` (modelo de interés) y `habeas_data_accepted` (permiso legal) antes de avanzar.
* **R3 - Cognitive Brake:** Detención absoluta en `calculate_credit_score`. Prohibido el uso de placeholders conversacionales ($X.XXX).

### Phase 2: Tríada RAG y IA-as-a-Judge (Consolidado)
* **R4 - Tracing Forense:** Integración mandatoria de Langfuse mediante el decorador `@observe` vinculado al teléfono del usuario.
* **R5 - Matriz de 9 Criterios:** El componente Juez debe evaluar y castigar la falta de imágenes, precios o solicitud de datos sin Habeas Data previo.
* **R6 - Fallback Profesional:** Mensajes de disculpa fluidos controlados por Firestore ante fallos de inferencia de la IA.

### Phase 3: Infraestructura Nativa Firebase y Sincronización Reactiva (En Desarrollo)
* **R7 - CRM Protected Fields:** El bot tiene prohibido modificar o degradar los campos financieros manuales del asesor (`approved_amount`, `monthly_quota`, `current_agent`) en la colección `prospectos`.
* **R8 - Real-Time Listening (Frontend):** La interfaz web del CRM debe suscribirse mediante `onSnapshot` al documento de Firebase para reflejar los datos del cliente en tiempo real sin recargar la página.
* **R9 - Zero-Silent-Failures de Persistencia:** Intercepción global y registro forense estructurado (`logger.exception`) ante retrasos o timeouts en la base de datos.

### Phase 4: Optimización y Seguridad / Red Teaming (Planificado)
* **R10 - Caché Semántica:** Respuestas automáticas para consultas frecuentes del catálogo con similitud coseno > 0.85 sin consumir tokens del LLM.
* **R11 - Prompt Injection Shield:** Pruebas de estrés para garantizar que ningún usuario pueda extraer datos o saltarse el muro de Habeas Data manipulando los mensajes de texto.

---
*Ultima actualización de sincronía: 2026-05-15*