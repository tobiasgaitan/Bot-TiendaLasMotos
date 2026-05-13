# DOCUMENTO MAESTRO - Bot Tienda Las Motos (v9.8.7)

## 1. Certificación de Versión
**Versión Actual:** v9.8.7 "Estado de Gracia Técnico"
**Fecha:** 2026-05-13
**Score de Coherencia:** 1.000 (Certificado por JudgeService v9.8.6)

## 2. Stack Tecnológico
- **Lenguaje:** Python 3.13 (Estricto)
- **Motor de IA:** Gemini 2.5 Flash
- **SDK:** `google-genai` v1.0.0
- **Observabilidad:** Langfuse (Tracing distribuido con `userId` y `sessionId`)
- **Infraestructura:** Google Cloud Run + Firestore + Meta WhatsApp Business API

## 3. Fuentes Únicas de Verdad (SSOT)
- **Configuración Dinámica:** Firestore `configuracion/juan_pablo_personality` (Primary).
- **Fallback Estático:** `app/core/prompts.py` (Mantiene paridad con v9.8.7).
- **Lógica Financiera:** `app/services/financial_service.py` (v1.5.0).
- **Reglas de Negocio:** `docs/BUSINESS_RULES.md`.

## 4. Matriz de Calidad (9 Criterios v9.8.7)
1.  **C1: Visual-Lock**: Toda recomendación DEBE incluir Precio ($) e Imagen.
2.  **C2: Paridad Financiera**: Solo usa cuotas devueltas por `calculate_credit_score`.
3.  **C3: Habeas Data Estricto**: Prohibido pedir datos sensibles sin `habeas_data_accepted=True`.
4.  **C4: Catalog-Lock (Flexibilizado)**: Prohibido inventar specs. Permitido mencionar COMPETENCIA (NKD, Boxer) para ofrecer equivalentes internos.
5.  **C5: One-Question-Rule**: Una sola pregunta por interacción para evitar abrumar al usuario.
6.  **C6: Consistencia de Scoring**: Uso de `search_catalog` con lógica de prioridad (Tiered Scoring v9.8.1).
7.  **C7: Protocolo Brilla**: Recolección de Cédula y Recibos para perfiles específicos.
8.  **C8: Ruta de Conversión**: El flujo debe avanzar hacia el handoff humano tras la simulación.
9.  **C9: City Discovery**: Obligatorio preguntar ciudad antes de cualquier cálculo financiero.

## 5. Protocolos de Seguridad y Blindaje
- **Cognitive Brakes:** Bloqueo de generación ante placeholders `$X.XXX`. El bot DEBE detenerse y esperar el JSON de la herramienta financiera.
- **Idempotencia (v9.8.3):** Filtro de mensajes duplicados en `app/routers/whatsapp.py` para evitar bucles de inferencia.
- **Memory Restoration (v9.8.3):** Restauración quirúrgica de sesiones con tracking de tareas asíncronas.
- **Catalog Interface Unification (v9.8.7):** Método unificado `search_catalog` en todos los servicios y herramientas.

## 6. Historial de Commits Críticos
- `bc6e8e4`: Unificación de interfaz `search_catalog` y reparación de referencias.
- `f0b825d`: Fix de mocks de memoria y restauración de integridad en CRM.

---
*Este documento es inmutable sin orden explícita del Auditor de Seguridad.*
