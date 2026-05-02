---
task: 001
name: Restauracion Entorno y Eval
description: "BOT-CORE-770-EVAL: Reparar permisos npm cache (EACCES root), inicializar STATE.md/ROADMAP.md y ejecutar suite de evaluación de no-regresión sobre God Nodes auditados."
ticket: BOT-CORE-770-EVAL
---

# Quick Task 001: Restauracion Entorno y Eval

## Objetivo

Restaurar el entorno de herramientas CLI reparando los permisos root-owned en `.npm/_cacache`,
inicializar los artefactos de estado del proyecto GSD (STATE.md, ROADMAP.md) y ejecutar la
suite de evaluación de no-regresión sobre los God Nodes auditados (ai_brain, whatsapp, memory_service).

## Diagnóstico Forense (PAA ejecutado)

- **CAUSA RAÍZ 1**: `.npm/_cacache` propiedad de `root:staff` → bloquea toda ejecución `npx` con EACCES.
- **CAUSA RAÍZ 2**: `agent-cli` no es un paquete npm público (confirmado en conversación d88e285e).
  El directorio `.agent/` existe pero solo contiene `VERSION` y `workflows/` — no hay binario instalado.
- **CAUSA RAÍZ 3**: `.planning/STATE.md` y `.planning/ROADMAP.md` ausentes — el motor GSD no tiene
  ancla de estado para el proyecto BOT-STRUC-765-EVOLUTION.

## Tasks

<task type="manual_approval">
  <name>Reparar permisos npm cache (EACCES)</name>
  <files>.npm/_cacache</files>
  <action>Ejecutar: sudo chown -R $(whoami) ~/.npm
  Requiere aprobación explícita del usuario (comando sudo).</action>
  <verify>ls -la ~/.npm/_cacache | head -3  # Owner debe ser tobiasgaitangallego, no root</verify>
  <done>_cacache owned por tobiasgaitangallego:staff</done>
</task>

<task type="auto">
  <name>Inicializar STATE.md y ROADMAP.md del proyecto</name>
  <files>.planning/STATE.md, .planning/ROADMAP.md</files>
  <action>Crear STATE.md con el estado actual del proyecto BOT-STRUC-765-EVOLUTION (último commit b4471b3)
  y ROADMAP.md con las fases completadas vs pendientes.</action>
  <verify>cat .planning/STATE.md | head -5  # Debe mostrar project y last_commit</verify>
  <done>Archivos creados con estado fidedigno del repositorio</done>
</task>

<task type="auto">
  <name>Suite de Evaluación de No-Regresión (God Nodes)</name>
  <files>app/routers/whatsapp.py, app/services/memory_service.py, app/ai_brain.py</files>
  <action>Ejecutar pytest sobre los test existentes de los God Nodes auditados.
  Si agent-cli eval no está disponible, ejecutar: python3 -m pytest tests/ -v --tb=short 2>&1</action>
  <verify>python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20</verify>
  <done>Todos los tests pasan. Reporte pegado en SUMMARY.md</done>
</task>

---
*Created: 2026-04-29*
