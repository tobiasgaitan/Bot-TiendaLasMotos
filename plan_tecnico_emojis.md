# Diagnóstico de Pérdida de Payload (Unicode/Emojis)

Tras realizar la arqueología de código en las capas de red, buffering y procesamiento de IA, se ha identificado el origen de la falla en la persistencia del flag de Habeas Data mediante emojis.

## Arqueología y Hallazgos

### 1. Capa de Red (`app/routers/whatsapp.py`)
- **Estado**: ✅ Funcional.
- **Detalle**: La función `_extract_message_data` utiliza `msg["text"]["body"]` para mensajes de texto. No hay filtros de regex ni decodificaciones destructivas en esta etapa. Los caracteres Unicode (emojis) entran al sistema intactos.
- **Excepción**: Las "Reacciones" (cuando el usuario reacciona a un mensaje) se mapean manualmente a la cadena `"Sí"`. Esto funciona para el flujo, pero si el usuario envía el emoji como un mensaje de texto normal, este sigue su ruta original.

### 2. Capa de Buffering (`app/services/message_buffer.py`)
- **Estado**: ✅ Funcional.
- **Detalle**: El buffer agrupa mensajes usando `" ".join(messages)`. No realiza normalización `NFC/NFKC` ni limpiezas de caracteres. El payload "👍" sobrevive al buffering.

### 3. Causa Raíz: El "Pivote de Competencia" y Fallo de Intención
- **Hallazgo Crítico**: El log `PHASE-GATE TRIGGERED` indica que la lógica de cumplimiento detectó que el campo `habeas_data_accepted` en Firestore sigue siendo `false`. 
- **Mecánica del Fallo**: En el Turno 1, cuando se invoca el pivote de competencia (`pulsar`), el sistema entra en un estado de alta temperatura o error de red que devuelve la respuesta de fallback ("Se me quedó colgado..."). 
- **Consecuencia**: Si la ejecución de `pensar_respuesta` falla o se interrumpe, el proceso de `generate_summary` (que es el encargado de extraer y persistir el JSON en Firestore) no se ejecuta o recibe un contexto incompleto. El anterior Hotfix en `json_processor.py` solo actúa **después** de que el LLM genera un JSON exitoso. Si el LLM no detecta el emoji como una aceptación dentro de su esquema de extracción debido a la distracción por el "pivote de competencia", el guardrail nunca se activa.

## Contrato JSON Inmutable (Actualizado)

Este contrato debe ser respetado estrictamente por el `Extractor PII Juan Pablo` en `ai_brain.py`.

```json
{
  "summary": "Resumen ejecutivo de la sesión",
  "extracted": {
    "name": "string",
    "city": "string",
    "moto_interest": "string",
    "moto_ofrecida": "string",
    "moto_aceptada": "string",
    "habeas_data_accepted": "boolean",
    "payment_method": "string",
    "ocupacion": "string",
    "datacredito": "string",
    "vivienda": "string",
    "servicios_publicos": "string"
  }
}
```

## Plan de Acción (Transform Phase)

### [Componente: app/services/ai_brain.py]

#### [MODIFY] [ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py)
- **Refuerzo de Prompt de Extracción**: Inyectar una instrucción explícita en `generate_summary` que obligue al modelo a priorizar la detección de emojis en el `conversation_text` para el campo `habeas_data_accepted`.
- **Mitigación de Latencia**: Revisar el timeout del cliente de AI para asegurar que la fase de extracción no muera silenciosamente ante un `search_catalog` lento.

### [Componente: app/utils/json_processor.py]

#### [MODIFY] [json_processor.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/utils/json_processor.py)
- **Hardening del Adaptador**: Se mantendrá la función `_ensure_boolean_integrity` pero se añadirá un log de auditoría interna para ver qué valor está llegando antes del casteo.

## Plan de Verificación

1. **Prueba End-to-End Local**: Simular un mensaje de texto con solo el emoji "👍" y verificar que el payload `extracted` devuelto por `generate_summary` contenga `True`.
2. **Auditoría de Logs**: Verificar que no aparezca el error `PHASE-GATE TRIGGERED` tras la aceptación.
