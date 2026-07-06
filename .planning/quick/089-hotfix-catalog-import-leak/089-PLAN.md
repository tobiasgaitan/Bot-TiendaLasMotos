---
task: 089
name: hotfix-catalog-import-leak
description: Exponer CatalogService en app/services/__init__.py e implementar un test de integración rígido en tests/test_agentic_loop_async.py para interceptar payloads hacia Meta y forzar fallos si contienen directivas internas o bypass silencioso.
---

# Quick Task 089: hotfix-catalog-import-leak

## Objective
Corregir la falta de importación de `CatalogService` en `app/services/__init__.py` para evitar `ImportError` e implementar un test de integración rígido en `tests/test_agentic_loop_async.py` que verifique que no haya fuga de contexto ni elusión de la herramienta `calculate_credit_score`.

## Tasks

<task type="auto">
  <name>Exponer CatalogService en __init__.py</name>
  <files>
    <file>app/services/__init__.py</file>
  </files>
  <action>Modificar app/services/__init__.py para importar y exportar explícitamente CatalogService.</action>
  <verify>python3 -c "from app.services import CatalogService; print(CatalogService.__file__)"</verify>
  <done>CatalogService se importa correctamente desde app.services sin lanzar ImportError.</done>
</task>

<task type="auto">
  <name>Implementar test de integración rígido en tests/test_agentic_loop_async.py</name>
  <files>
    <file>tests/test_agentic_loop_async.py</file>
  </files>
  <action>Agregar test_meta_payload_leak_prevention en tests/test_agentic_loop_async.py. El test simulará llamadas al webhook y asertará mediante Regex que el payload de salida hacia Meta no contenga directivas internas del sistema (como "EL USUARIO ESTÁ LISTO PARA EL CRÉDITO") ni bypass silencioso de la simulación de cuotas ciegas.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>El nuevo test de integración pasa exitosamente y detecta fugas simuladas.</done>
</task>

---
*Created: 2026-07-02*
