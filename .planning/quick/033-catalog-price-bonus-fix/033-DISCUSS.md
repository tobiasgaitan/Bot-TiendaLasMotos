# Documento Técnico de Planificación (BOT-BE-53)

## 1. Arquitectura y Decisiones de Diseño

Para resolver el fallo crítico de colisión de nomenclatura y asegurar la serialización y validación correcta del bono en la ventana de contexto del LLM, se implementa una capa robusta en `CatalogService`:

- **Nomenclatura Única (Inmutabilidad):** Se fuerza la extracción de la base canónica mediante `price_val = data.get("price") or 0`, rechazando fallbacks no normalizados.
- **Normalización de Bonos:** Se extraen `bonusAmount` (como `int`) y `bonusEndDate` (objeto Firestore Timestamp, `datetime` o `str`) en `load_catalog()`.
- **Validación Activa de Bonos:** En la serialización a través de `search_items` (que produce `truncated_item`) y `search_catalog`, se evalúa la vigencia de `bonusEndDate` comparando contra la fecha del servidor actual (`datetime.now()`). Si el bono ha expirado o su monto es <= 0, se fuerza `bonusAmount = 0` y `bonusEndDate = None` para evitar la contaminación de datos del simulador de crédito.
- **Mutación Visual en Markdown:** Si el bono está vigente, el string resultante en `search_catalog` mutará inyectando explícitamente `[BONO EXCLUSIVO DE CONTADO: $X válido hasta Y]`.

---

## 2. Esquemas y Contratos de Datos (JSON Voorhees)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CatalogServiceSchema",
  "description": "Contratos y esquemas de datos para el precio y bonos de CatalogService (BOT-BE-53)",
  "firestore_document_schema": {
    "type": "object",
    "properties": {
      "price": {
        "type": "integer",
        "description": "Precio base canónico de la motocicleta en Firestore"
      },
      "bonusAmount": {
        "type": "integer",
        "description": "Monto del bono de descuento de contado"
      },
      "bonusEndDate": {
        "type": ["string", "object", "integer"],
        "description": "Fecha de vigencia del bono (String ISO, datetime, Firestore Timestamp o epoch)"
      }
    },
    "required": ["price"]
  },
  "mapped_item_schema": {
    "type": "object",
    "properties": {
      "id": { "type": "string" },
      "name": { "type": "string" },
      "price": { "type": "integer" },
      "formatted_price": { "type": "string" },
      "category": { "type": "string" },
      "image_url": { "type": "string" },
      "active": { "type": "boolean" },
      "description": { "type": "string" },
      "specs": { "type": "string" },
      "link": { "type": "string" },
      "search_tokens": { "type": "array", "items": { "type": "string" } },
      "search_text": { "type": "string" },
      "searchBy": { "type": "array", "items": { "type": "string" } },
      "cc": { "type": "integer" },
      "bonusAmount": { "type": "integer" },
      "bonusEndDate": { "type": ["string", "object", "integer", "null"] }
    },
    "required": [
      "id",
      "name",
      "price",
      "formatted_price",
      "category",
      "image_url",
      "bonusAmount",
      "bonusEndDate"
    ]
  },
  "truncated_item_schema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "price": { "type": "string" },
      "raw_price": { "type": "integer" },
      "formatted_price": { "type": "string" },
      "category": { "type": "string" },
      "image_url": { "type": "string" },
      "searchBy": { "type": "array", "items": { "type": "string" } },
      "summary": { "type": "string" },
      "bonusAmount": { "type": "integer" },
      "bonusEndDate": { "type": ["string", "null"] }
    },
    "required": [
      "name",
      "price",
      "raw_price",
      "formatted_price",
      "category",
      "image_url",
      "searchBy",
      "summary",
      "bonusAmount",
      "bonusEndDate"
    ]
  },
  "search_catalog_output_contract": {
    "type": "string",
    "description": "String formateado en Markdown conteniendo los resultados. Los ítems con bono activo formatean como: - Nombre (categoria): precio [BONO EXCLUSIVO DE CONTADO: $X válido hasta Y]"
  }
}
```
