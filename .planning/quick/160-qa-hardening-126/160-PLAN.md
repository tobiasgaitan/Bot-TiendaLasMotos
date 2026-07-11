---
task: 160
name: QA Hardening — 3 Falsos Positivos BOT-QA-HARDENING-126
description: Eliminar 3 falsos positivos críticos en test_pcc_ficha_tecnica.py que enmascaran fallos de runtime real.
---

# Quick Task 160: QA Hardening — BOT-QA-HARDENING-126

## Objetivo
Endurecer tres pruebas que pasan localmente por entornos de mock higienizados pero enmascaran
regresiones críticas en producción: alucinación de ficha técnica silenciosa, mutilación de URLs
complejas por proxy Meta, y aceptación errónea de marcadores "Sin descripción" en Visual-Lock.

## Tareas

<task type="auto">
  <name>Tarea 1: KeyError duro en search_catalog al mutar llaves obligatorias</name>
  <files>app/services/catalog_service.py</files>
  <action>
    Modificar la línea 794 de search_catalog: si m.get('summary') devuelve None (no simplemente
    ausente — verificar con 'summary' in m and m['summary'] is None), elevar un KeyError explícito
    en lugar de omitir silenciosamente. Adicionalmente endurecer test_pcc_ficha_tecnica_no_silent_null
    en test_pcc_ficha_tecnica.py para que el Escenario 2 inyecte un item con summary=None (no solo
    ausente) y verifique que search_catalog lanza KeyError.
  </action>
  <verify>python3 -m pytest tests/test_pcc_ficha_tecnica.py::test_pcc_ficha_tecnica_no_silent_null -xvs 2>&1 | tail -20</verify>
  <done>Test pasa y demuestra KeyError propagado correctamente</done>
</task>

<task type="auto">
  <name>Tarea 2: Transformador dinámico de URL Meta en test_habeas_data_gate_before_credit_score</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>
    Inyectar en el mock_catalog del Caso 2 (con consentimiento) una URL compleja simulando
    parámetros de red Meta: "https://img.url?token=abc123&size=800&watermark=tlm". Agregar un
    transformador que verifique que si la URL contiene query params (caracteres '?' y '&'), el
    sistema no falla silenciosamente. El test debe afirmar que la URL de imagen en la respuesta
    Ficha Tecnica no está vacía incluso con URL compleja.
  </action>
  <verify>python3 -m pytest tests/test_pcc_ficha_tecnica.py::test_habeas_data_gate_before_credit_score -xvs 2>&1 | tail -30</verify>
  <done>Test pasa con URL compleja inyectada y aserción HTTP 400 controlada</done>
</task>

<task type="auto">
  <name>Tarea 3: Rechazo estricto de 'Sin descripción' bajo Visual-Lock íntegro</name>
  <files>tests/test_pcc_ficha_tecnica.py, app/services/agentic_loop_service.py</files>
  <action>
    Modificar test_resilience_missing_summary_passes_filter para que el prospect tenga
    moto_interest activo. Agregar aserción de que run_checker rechaza respuestas con
    "Ficha Tecnica: Sin descripción" cuando hay intención comercial activa.
    Modificar run_checker en agentic_loop_service.py para detectar el marcador 'Sin descripción'
    como fallo de Visual-Lock cuando has_moto_interest=True.
  </action>
  <verify>python3 -m pytest tests/test_pcc_ficha_tecnica.py::test_resilience_missing_summary_passes_filter -xvs 2>&1 | tail -30</verify>
  <done>Test rechaza 'Sin descripción' con intención comercial y pasa sin moto_interest</done>
</task>

---
*Created: 2026-07-11*
