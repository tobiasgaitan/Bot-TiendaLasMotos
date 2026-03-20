import json

from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

# The schema from ai_brain.py
extraction_schema = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "description": "Un resumen conciso (1-2 oraciones) del tema principal y datos clave de la conversación."
        },
        "extracted": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Nombre si se mencionó. IGNORA el nombre 'Juan Pablo', 'Auteco' o referencias al bot. SOLO extrae si el usuario se presenta a sí mismo."
                },
                "city": {
                    "type": "STRING",
                    "description": "Ciudad si se mencionó (ej. Bogotá, Medellín)."
                },
                "payment_method": {
                    "type": "STRING",
                    "description": "Método de pago si se mencionó (ej. crédito, contado, brilla, no sé)."
                },
                "moto_interest": {
                    "type": "STRING",
                    "description": "ÚNICAMENTE referencias, marcas o estilos reales de motos (ej. Boxer, Pulsar, NKD, Scooter, Deportiva). IGNORA términos financieros."
                },
                "ocupacion": {
                    "type": "STRING",
                    "description": "Ocupación o tipo de contrato laboral si se mencionó (ej. Empleado, Independiente, Estudiante, Pensionado)."
                },
                "datacredito": {
                    "type": "STRING",
                    "description": "Estado o historial en Datacrédito si se mencionó (ej. Al día, Reportado, Sin experiencia, Castigado)."
                },
                "vivienda": {
                    "type": "STRING",
                    "description": "Tipo de vivienda o situación de gastos de vivienda si se mencionó (ej. Arriendo, Familiar, Propia)."
                },
                "servicios_publicos": {
                    "type": "STRING",
                    "description": "Si tiene servicios públicos como Gas Natural a su nombre o plan de celular si se mencionó."
                }
            }
        }
    }
}

full_prompt = JUAN_PABLO_SYSTEM_INSTRUCTION + "\n\n<EXTRACTION_SCHEMA>\n" + json.dumps(extraction_schema, indent=2, ensure_ascii=False) + "\n</EXTRACTION_SCHEMA>\n"

with open("tmp_prompt_to_sync.txt", "w", encoding="utf-8") as f:
    f.write(full_prompt)

print("Prompt consolidado generado en tmp_prompt_to_sync.txt")
