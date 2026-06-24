---
task: 064
name: hotfix-brain-e2e-fallback
description: "[BOT-ARQ-E2E-095] Blindar evaluate_profile y métodos dependientes de 'partners' en FinancialService con try/except + logger.exception + fallbacks seguros. Escribir test E2E que simule Firestore vacío."
---

# Quick Task 064: hotfix-brain-e2e-fallback

## Objective
Blindar FinancialService.evaluate_profile, la propiedad link_brilla y _generate_generic_response
contra un esquema de configuración vacío de Firestore, asegurando Zero-Silent-Failures y
que el flujo E2E de cuotas retorne HTTP 200 con logs forenses válidos.

## Tasks

<task type="auto">
  <name>Blindar evaluate_profile con try/except + fallbacks en partners.get()</name>
  <files>app/services/financial_service.py</files>
  <action>
    Envolver el bloque `partners = self._config_service.get_partners_config()` en un
    try/except con logger.exception explícito. Usar .get() con fallback "#" garantizado
    en todos los puntos de acceso a 'partners'. Blindar también `link_brilla` property
    y `_generate_generic_response`.
  </action>
  <verify>python3 -c "from app.services.financial_service import FinancialService; fs = FinancialService(); print(fs.evaluate_profile(ocupacion_y_contrato='Empleado fijo', ingresos_demostrables='1200000', historial_datacredito='Al dia'))"</verify>
  <done>evaluate_profile retorna un dict coherente sin colapso incluso con config vacío</done>
</task>

<task type="auto">
  <name>Test E2E en test_agentic_loop_async.py con mock de Firestore vacío</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>
    Añadir test_evaluate_profile_empty_firestore_config que mockee config_service
    para devolver {} en get_partners_config, get_financial_entity_config y
    get_financial_matrix. Simular flujo completo de cuotas. Asegurar HTTP 200
    (sin excepción), cuota_mensual > 0, y verificar que se genera log forense.
  </action>
  <verify>python3 -m pytest tests/test_agentic_loop_async.py -v 2>&1 | tail -30</verify>
  <done>Todos los tests de test_agentic_loop_async.py pasan con PASSED</done>
</task>

---
*Created: 2026-06-24*
