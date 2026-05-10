---
task: 021
name: Cognitive Brakes & Placeholder Sanitization
description: Implementación de 'Frenos Cognitivos' en ai_brain.py para forzar detención durante Function Calling financiero y bloquear placeholders $X.XXX.
---

# Quick Task 021: Cognitive Brakes & Placeholder Sanitization

## Objective
Implementar el protocolo "The Law of Cognitive Brakes" (Fase 4, Guardrail #6) para evitar que la IA emita valores monetarios placeholder ($X.XXX) antes de recibir el JSON real de Crediorbe/Motor Financiero.

## Diagnóstico (Arqueología Completada)
- **Commit 9027f8e**: Inyectó directiva parcial solo en `FunctionDeclaration.description` (L546).
- **L1009**: `cuota_str = "$X.XXX"` — placeholder literal que se emite si `m_price == 0`.
- **Falta**: Guardrail post-generación en `pensar_respuesta` que bloquee placeholders.
- **Falta**: Directiva de interrupción en el prompt XML inyectado durante PHASE_3.

## Tasks

<task type="auto">
  <name>T1: Eliminar placeholder "$X.XXX" del código fuente</name>
  <files>app/services/ai_brain.py</files>
  <action>
    Reemplazar la lógica de L1009 para que cuando `m_price == 0`, NO se inyecte "$X.XXX" sino un mensaje que fuerce al LLM a NO mencionar cuotas específicas y diga que calculará cuando tenga los datos completos.
  </action>
  <verify>grep -n 'X\.XXX' app/services/ai_brain.py | wc -l == 0</verify>
  <done>No existen placeholders $X.XXX en el código fuente.</done>
</task>

<task type="auto">
  <name>T2: Inyectar Cognitive Brake en prompt PHASE_3</name>
  <files>app/services/ai_brain.py</files>
  <action>
    En la sección `funnel_instruction` de PHASE_3_CREDIT_PROFILING (L668), inyectar la directiva de interrupción completa: "Ejecuta la herramienta calculate_credit_score. ¡DETENTE AQUÍ! No generes texto de respuesta. Espera el resultado interno de la herramienta."
  </action>
  <verify>grep -c 'DETENTE AQUÍ' app/services/ai_brain.py >= 2 (FunctionDeclaration + funnel_instruction)</verify>
  <done>Directiva de interrupción presente en FunctionDeclaration Y en funnel_instruction de Phase 3.</done>
</task>

<task type="auto">
  <name>T3: Guardrail post-generación contra placeholders financieros</name>
  <files>app/services/ai_brain.py</files>
  <action>
    En `pensar_respuesta`, después del `clean_parrot_phrases` (L412), agregar un regex que detecte patrones de placeholder financiero ($X.XXX, $X.XXX.XXX) y los reemplace con un mensaje seguro de "calculando tu plan personalizado".
  </action>
  <verify>python3 -c "import re; p=r'\\\$X[\\.X]+'; assert re.search(p, '\$X.XXX'); print('REGEX OK')"</verify>
  <done>Guardrail regex bloquea emisión de placeholders al usuario final.</done>
</task>

---
*Created: 2026-05-10*
