---
task: 183
name: Re-arquitectura del pipeline financiero
description: Refactorizar app/services/financial_service.py para implementar con precisión la lógica de calculator.ts para Brilla de Gases
---

# Quick Task 183: Re-arquitectura del pipeline financiero

## Objective
Refactorizar la lógica financiera de `app/services/financial_service.py` para sincronizarla con `calculator.ts`, estableciendo `p1_base`, calcular `vGestion`, `p2_intermediate`, `vCobertura`, `cuota_aval_mensual`, `P_final`, y asegurar que la cuota final en WhatsApp sume todos los componentes necesarios del Año 1.

## Tasks

<task type="auto">
  <name>Refactorizar financial_service.py</name>
  <files>app/services/financial_service.py</files>
  <action>Refactorizar la lógica en calculate_payment para Brilla de Gases implementando la cascada de redondeo con bases correctas: p1_base = precio - inicial, vGestion = round(p1_base * managementRate/100, 0), p2_intermediate = p1_base + vGestion, vCobertura = round(p2_intermediate * coverageRate/100, 0), cuota_aval_mensual = round(vCobertura/12, 0), P_final = p2_intermediate + registro, y cuota_mensual sumando cuota_aval_mensual y seguro_vida para el Año 1.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>La lógica financiera implementa con precisión milimétrica los redondeos e intermediaciones de calculator.ts y pasa las pruebas.</done>
</task>

<task type="auto">
  <name>Refactorizar tests/test_pcc_ficha_tecnica.py</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>Eliminar mocks estáticos de cuotas en tests/test_pcc_ficha_tecnica.py, instanciar el servicio financiero real y realizar aserciones rigurosas para Victory Bet ABS ($748.844) y TVS Sport 100 ELS ($364.825) bajo sus iniciales correspondientes.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Todos los mocks estáticos en test_pcc_ficha_tecnica.py han sido removidos y las aserciones de cuota de Victory Bet ABS y TVS Sport 100 ELS son exactas.</done>
</task>
