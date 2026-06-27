---
task: 077
name: Calibrar umbrales de latencia k6 para flujo LLM+Firestore
description: Ajustar thresholds de http_req_duration en test_k6.js a valores realistas para un agente de IA generativa (p95<15s, p99<20s)
---

# Quick Task 077: Calibrar umbrales de latencia k6

## Objetivo
Corregir el Gate de Rendimiento del pipeline QA que falla porque los umbrales de latencia (`p(95)<250ms`, `p(99)<450ms`) son irreales para un flujo de webhook que ejecuta llamadas síncronas pesadas a Gemini LLM y Firestore. La latencia real p(95) bajo carga fue de **10.82 segundos**.

## Análisis Forense
- **Archivo:** `tests/performance/test_k6.js`, línea 14
- **Valor actual:** `http_req_duration: ['p(95)<250', 'p(99)<450']`
- **Valor objetivo:** `http_req_duration: ['p(95)<15000', 'p(99)<20000']`
- **Justificación:** El flujo webhook→HMAC→Gemini→Firestore involucra un round-trip a un LLM generativo con latencias inherentes de 5-12s. Los umbrales de 250ms son propios de APIs CRUD sin dependencias externas pesadas.
- **Alcance:** Solo se modifica el bloque `thresholds.http_req_duration`. La métrica `tasa_errores_webhook` permanece inalterada.

## Tasks

<task type="auto">
  <name>Ajustar thresholds http_req_duration</name>
  <files>tests/performance/test_k6.js</files>
  <action>Reemplazar `'p(95)<250', 'p(99)<450'` por `'p(95)<15000', 'p(99)<20000'` en la línea 14</action>
  <verify>grep -n 'http_req_duration' tests/performance/test_k6.js</verify>
  <done>La línea muestra p(95)<15000 y p(99)<20000</done>
</task>

---
*Created: 2026-06-27T04:40:00Z*
