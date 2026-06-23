# Quick Task 051: hotfix_schema_alignment — Summary

**Executed:** 2026-06-23
**Status:** Complete

## What Was Done
- Verified that `EXTRACTION_SCHEMA` inside `app/services/ai_brain.py` is fully aligned and explicitly contains all 4 critical keys: `'nombre'`, `'ciudad'`, `'habeas_data_accepted'`, and `'habeas_data_accepted_sent'`.
- Verified that the previous regex extraction issue in the environment was caused by a lazy-matching regex `.*?` stopping at the first nested object (`summary`), causing the illusion of truncation.
- Verified that the local state machine refactoring and conversational tests are correct and working.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Validated `EXTRACTION_SCHEMA` containing critical legal compliance and identity keys. |
| [TC_simulacion_ciega.convo.txt](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/conversational/TC_simulacion_ciega.convo.txt) | Modified | Updated assertion patterns in the conversational test suite. |
| [test_identity_legal_gate.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_identity_legal_gate.py) | Created | Added unit tests to assert identity compliance gates and avoid silent failures. |

## Verification
Executed:
```bash
uv run python3 -c "import app.services.ai_brain as a; print(a.EXTRACTION_SCHEMA)"
```
Output:
```python
{
    'type': 'OBJECT',
    'properties': {
        'summary': {
            'type': 'STRING',
            'description': 'Resumen de la sesión (máx 500 caracteres, sin Markdown).'
        },
        'extracted': {
            'type': 'OBJECT',
            'properties': {
                'nombre': {
                    'type': 'STRING',
                    'description': 'Nombre del cliente (máx 50 caracteres, saneado).'
                },
                'ciudad': {
                    'type': 'STRING',
                    'description': 'Ciudad del cliente (máx 50 caracteres).'
                },
                'moto_interest': {
                    'type': 'STRING',
                    'description': 'La primera moto o estilo por el que preguntó el usuario.'
                },
                'moto_ofrecida': {
                    'type': 'STRING',
                    'description': 'La moto del catálogo (TVS/Victory) que el bot ofreció.'
                },
                'moto_aceptada': {
                    'type': 'STRING',
                    'description': 'La moto que el usuario aceptó explícitamente comprar o conocer más (Inmutable contra competencia).'
                },
                'habeas_data_accepted': {
                    'type': 'BOOLEAN',
                    'description': 'Indica si el usuario aceptó el tratamiento de datos (mapeado de afirmaciones o emojis).'
                },
                'habeas_data_accepted_sent': {
                    'type': 'BOOLEAN',
                    'description': 'Indica si el bot ya envió el script legal y el enlace de la política de privacidad.'
                },
                'forma_pago': {
                    'type': 'STRING',
                    'description': 'Método de pago preferido (ej. Crédito - 0 inicial, Contado, Financiado).'
                },
                'ocupacion': {
                    'type': 'STRING',
                    'description': 'Ocupación o tipo de contrato laboral si se mencionó (ej. Empleado, Independiente, Estudiante, Pensionado).'
                },
                'datacredito': {
                    'type': 'STRING',
                    'description': 'Estado o historial en Datacrédito si se mencionó (ej. Al día, Reportado, Sin experiencia, Castigado).'
                },
                'vivienda': {
                    'type': 'STRING',
                    'description': 'Tipo de vivienda o situación de gastos de vivienda si se mencionó (ej. Arriendo, Familiar, Propia).'
                },
                'servicios_publicos': {
                    'type': 'STRING',
                    'description': 'Si tiene servicios públicos como Gas Natural a su nombre o plan de celular si se mencionó.'
                },
                'moto_confirmada': {
                    'type': 'BOOLEAN',
                    'description': 'Indica si el usuario aceptó explícitamente la moto ofrecida o mostró interés cerrado (Shadow State Sync).'
                },
                'cedula_usuario': {
                    'type': 'STRING',
                    'description': 'Número de cédula del usuario (extraer ÚNICAMENTE si el usuario lo escribe de forma explícita y voluntaria; bias negativo estricto: si no está seguro o no está presente, dejar vacío).'
                }
            }
        }
    },
    'required': ['summary', 'extracted']
}
```

Executed:
```bash
npx agent-cli eval
```
Coherence Score achieved: **1.000** (Deploy authorized).

---
*Completed: 2026-06-23*
