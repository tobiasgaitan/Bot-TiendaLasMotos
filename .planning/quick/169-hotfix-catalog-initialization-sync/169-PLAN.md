---
task: 169
name: Hotfix Catalog Initialization Sync
description: Refactorizar CatalogService.initialize para recibir ConfigLoader como dependencia inyectada, eliminar instanciacion silenciosa dentro de load_catalog(), y agregar guardrail RuntimeError fail-fast si aliases no se hidratan.
---

# Quick Task 169: Hotfix Catalog Initialization Sync

## Objective
Eliminar la condicion de carrera en CatalogService.load_catalog donde ConfigLoader() es instanciado sin `db`, resultando en `category_aliases = {}` cuando el singleton no esta hidratado. Convertir ConfigLoader en dependencia inyectada desde app/main.py y agregar guardrail fail-fast.

## Tasks

<task type="auto">
  <name>Refactorizar CatalogService.initialize y load_catalog</name>
  <files>app/services/catalog_service.py</files>
  <action>
    1. Agregar parametro `config_loader` opcional a initialize(db, config_loader=None)
    2. Almacenarlo en self._config_loader
    3. En load_catalog(), usar self._config_loader si disponible; si no, intentar obtener el singleton ya hidratado
    4. Si config_loader está disponible pero category_aliases resultan vacíos, lanzar RuntimeError fail-fast
  </action>
  <verify>python3 -c "from app.services.catalog_service import CatalogService; c = CatalogService(); print('OK')"</verify>
  <done>CatalogService acepta config_loader en initialize(), load_catalog() usa la dependencia inyectada, RuntimeError si aliases vacíos post-hidratación</done>
</task>

<task type="auto">
  <name>Actualizar app/main.py para inyectar config_loader</name>
  <files>app/main.py</files>
  <action>Pasar el config_loader ya hidratado como argumento a catalog_service.initialize(db, config_loader) en ambos paths (module-level y lifespan)</action>
  <verify>python3 -c "import ast; ast.parse(open('app/main.py').read()); print('Syntax OK')"</verify>
  <done>app/main.py pasa config_loader a catalog_service.initialize() en todos los paths de arranque</done>
</task>

<task type="auto">
  <name>Crear test test_catalog_initialization_failure</name>
  <files>tests/test_catalog_initialization_sync.py</files>
  <action>Crear test que verifica que CatalogService lanza RuntimeError si ConfigLoader no hidrató los aliases correctamente (simulando aliases vacíos después de load_all)</action>
  <verify>python3 -m pytest tests/test_catalog_initialization_sync.py -v</verify>
  <done>Test pasa verificando comportamiento fail-fast</done>
</task>

---
*Created: 2026-07-12*
