---
task: 099
name: bot-brain-alignment
description: Inyección de sinónimos regionales, purga de prompt zombie, hard-cap de tools y TTL en Cloud Tasks
---

# Quick Task 099: Bot Brain Alignment

## Objective
Resolver 4 fallos críticos: tubería semántica rota, desfase prompt-herramienta, bucle agéntico sin límite, y webhooks zombi.

## Tasks

Task 1: Inyectar category_aliases en System Prompt
- Files: app/services/config_service.py, app/services/ai_brain.py
- Action: Agregar getter en config_service, inyectar bloque XML dinámico en full_prompt
- Verify: python -m pytest app/tests/ -v --tb=short
- Done: El prompt audit log incluye diccionario_sinonimos_regionales

Task 2: Purga condicional REGLA DE CREDITO CIEGO
- Files: app/services/ai_brain.py
- Action: Detectar ausencia de calculate_credit_score en toolset y purgar instrucción del prompt
- Verify: python -m pytest app/tests/ -v --tb=short
- Done: En PHASE_1 el prompt NO contiene REGLA DE CREDITO CIEGO

Task 3: Hard-cap 2 function calls por turn
- Files: app/services/ai_brain.py
- Action: Truncar function_calls a máximo 2 por iteración del tool loop
- Verify: python -m pytest app/tests/ -v --tb=short
- Done: Log HARD-CAP se emite si LLM despacha >2 calls

Task 4: TTL 120s en Cloud Tasks + doc de resiliencia
- Files: app/routers/whatsapp.py
- Action: Agregar dispatch_deadline=120s al task payload
- Verify: python -m pytest app/tests/ -v --tb=short
- Done: El task payload incluye dispatch_deadline de 120s

---
Created: 2026-07-03
