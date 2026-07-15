---
task: 184
name: Financial Cascading Exact Parity
description: Refactor financial initialization logic to admit transparently both commercial net price and full catalog price, reaching $550.469 COP parity.
---

# Plan Técnico de Planificación: [BOT-BACKEND-FINANCIAL-CASCADING-EXACT-PARITY-184]

## 1. Arquitectura y Contratos JSON (Verdad Inmutable)

### Contrato de la API de Simulación (`calculate_payment`)

```json
{
  "input": {
    "precio": {
      "type": "number",
      "description": "Precio comercial neto (ej. 9399000) o integrado de catálogo full (ej. 10179000)"
    },
    "inicial": {
      "type": "number",
      "description": "Cuota inicial aportada por el cliente"
    },
    "plazo_meses": {
      "type": "integer",
      "description": "Plazo en meses del crédito"
    },
    "entidad": {
      "type": "string",
      "description": "Entidad financiera (ej. Brilla de Gases)"
    },
    "moto_cc": {
      "type": "number",
      "description": "Cilindraje de la moto"
    },
    "category": {
      "type": "string",
      "description": "Categoría de la moto (ej. motos)"
    }
  },
  "output_parity_kymco": {
    "cuota_mensual": 550469.0,
    "total_pagar": 13211256.0,
    "capital_financiado": 9619155.0,
    "seguro_vida": 15000.0,
    "cuota_aval": 32064.0,
    "plazo_meses": 24,
    "entidad": "Brilla de Gases",
    "uso_matriz": true
  }
}
```

## 2. Tareas Propuestas

<task type="auto">
  <name>Refactorizar lógica de inicialización del precio en financial_service.py</name>
  <files>
    - [financial_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/financial_service.py)
  </files>
  <action>
    Modificar `calculate_payment` para que al usar Brilla de Gases, resuelva el precio de catálogo de la moto a partir de `catalog_service`. Si el precio es catalog full (precio >= expected_net_price + reg_cost - 10000), descontar reg_cost dos veces del precio para obtener base_price (ya que la cascada vuelve a sumar reg_cost como docsTotal y en assetPrice). Si el precio es commercial net (precio >= expected_net_price - 10000), descontar reg_cost una vez. Actualizar monto_base consecuentemente.
  </action>
  <verify>.venv/bin/python3 -c "import app.main; from app.services.financial_service import financial_service; print(financial_service.calculate_payment(precio=10179000, inicial=1017900, plazo_meses=24, entidad='Brilla de Gases', moto_cc=124.6, category='motos'))"</verify>
  <done>La cuota calculada es exactamente $550.469 COP tanto al pasar precio=10179000 como precio=9399000 con inicial=1017900 y cc=124.6.</done>
</task>

<task type="auto">
  <name>Desarrollar prueba unitaria rígida en test_pcc_ficha_tecnica.py</name>
  <files>
    - [test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py)
  </files>
  <action>
    Añadir el test `test_agility_fusion_exact_parity` en `tests/test_pcc_ficha_tecnica.py` que valide que al llamar a `calculate_payment` o a `_calculate_payment_helper` con precio=10179000 (catálogo full) e inicial=1017900 y cc=124.6, la cuota resultante es estrictamente 550469.0.
  </action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py -k test_agility_fusion_exact_parity</verify>
  <done>La prueba unitaria corre y pasa exitosamente.</done>
</task>

<task type="auto">
  <name>Ejecutar pruebas completas y verificar Coherence Score de 1.000</name>
  <files>
    - [test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py)
  </files>
  <action>
    Correr pytest completo y ejecutar npx agent-cli eval para certificar el score.
  </action>
  <verify>npx agent-cli eval</verify>
  <done>Todas las pruebas pasan con score unificado de 1.000.</done>
</task>
