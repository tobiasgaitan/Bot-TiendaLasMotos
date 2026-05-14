---
task: 025
name: BOT-BUG-2.1 — JudgeService Parity Fix & ScoringService Substring Fix
description: Corregir brecha de validación en C2 (Parity) y falso positivo de subcadena en ScoringService._get_points
---

# Quick Task 025: BOT-BUG-2.1 — JudgeService Parity & Scoring Fix

## Objective
Cerrar la brecha en `_check_financial_parity` para que valide montos reales contra `FinancialService.calculate_payment`
con margen < 1%, y corregir `ScoringService._get_points` para usar coincidencia por palabra completa (`\b`) evitando
que "no reportado" coincida con "reportado".

## Análisis Forense (verificado físicamente)

### Bug 1 — `judge_service.py` L153-158: `_check_financial_parity`
La implementación actual **solo detecta el literal `$X.XXX`** (placeholder). No extrae el monto real de la respuesta
ni lo contrasta con `financial_service.calculate_payment`. Una cuota falsa como `$9.999.999` pasa la validación.

### Bug 2 — `scoring_service.py` L102-111: `_get_points` fallback de subcadena
El paso 3 del fallback usa `if k in key` → "reportado" está contenido en "no reportado", devolviendo 0 pts
en lugar del default 500. Esto causa un false-negative que propaga un score incorrecto.

## Contrato JSON Voorhees (Inmutable)

```json
{
  "judge_service._check_financial_parity": {
    "input": {"text": "str", "prospect_data": "Dict"},
    "extraction_regex": "\\$(\\d{1,3}(?:\\.\\d{3})*)(?:\\s*(?:/\\s*mes|mensual))?",
    "cross_validation": {
      "method": "financial_service.calculate_payment",
      "params": ["precio", "inicial", "plazo_meses"],
      "data_source": "prospect_data.financial_context",
      "margin_pct": 1.0
    },
    "output": ["Tuple[bool, str]"],
    "rejection_code": "C2_FINANCIAL_PARITY"
  },
  "scoring_service._get_points": {
    "fix": "Replace substring `if k in key` with `re.search(r'\\b' + re.escape(k) + r'\\b', key)`",
    "rationale": "Previene que 'reportado' coincida con 'no reportado' via substring"
  }
}
```

## Tasks

<task type="auto">
  <name>Fix 1: _check_financial_parity — Cross-Validation Real</name>
  <files>app/services/judge_service.py</files>
  <action>
    Reemplazar el cuerpo de `_check_financial_parity` (líneas 153-158) con:
    1. Detectar placeholder `$X.XXX` → REJECT (mantener).
    2. Extraer montos con formato `$X.XXX.XXX` de la respuesta.
    3. Si hay `financial_context` en prospect_data (precio, inicial, plazo_meses), llamar
       `financial_service.calculate_payment(...)` y comparar cada monto extraído.
    4. Si la diferencia > 1% → REJECT con código C2_FINANCIAL_PARITY.
    5. Si no hay contexto financiero, dejar pasar (sin datos no se puede validar).
  </action>
  <verify>python3 -m pytest tests/test_judge_service.py -k "parity" -v</verify>
  <done>El test `test_judge_financial_parity_fake_quota_rejected` falla antes del fix y pasa después.</done>
</task>

<task type="auto">
  <name>Fix 2: ScoringService._get_points — Word-Boundary Regex</name>
  <files>app/services/scoring_service.py</files>
  <action>
    Reemplazar el paso 3 de `_get_points` (for loop con `if k in key`) por un re.search con `\b` 
    para coincidir solo palabras completas.
  </action>
  <verify>python3 -m pytest tests/test_scoring_service.py -v 2>/dev/null || python3 -m pytest tests/ -k "scoring" -v</verify>
  <done>El scoring de "no reportado" devuelve el default (500) en lugar de 0.</done>
</task>

<task type="auto">
  <name>Test: Certificar rechazo C2_FINANCIAL_PARITY con mock</name>
  <files>tests/test_judge_service.py</files>
  <action>
    Agregar test `test_judge_financial_parity_fake_quota_rejected` que inyecta cuota falsa en la respuesta
    y verifica REJECTED C2_FINANCIAL_PARITY.
  </action>
  <verify>python3 -m pytest tests/test_judge_service.py -v</verify>
  <done>Suite completa pasa sin regresiones.</done>
</task>

---
*Created: 2026-05-14*
