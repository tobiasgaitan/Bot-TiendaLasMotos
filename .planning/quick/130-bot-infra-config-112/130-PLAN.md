---
task: 130
name: Correct Env Var Precedence for MIN_CATALOG_ITEMS
description: La variable de entorno MIN_CATALOG_ITEMS inyectada externamente en Cloud Run es ignorada o sobreescrita por valores locales dentro del contenedor, manteniendo el umbral de bloqueo en 60 ítems.
---

# Quick Task 130: Correct Env Var Precedence for MIN_CATALOG_ITEMS

## Objective
Ensure the settings loader prioritizes the externally injected environment variable MIN_CATALOG_ITEMS (retrieved from GCP Cloud Run) before reading any local dotenv configs, defaulting to 40.

## Tasks

<task type="auto">
  <name>Modify Settings constructor and load_dotenv placement</name>
  <files>app/core/config.py</files>
  <action>Remove module-level load_dotenv() and call it inside Settings.__init__ after reading MIN_CATALOG_ITEMS from the host environment. Set self.min_catalog_items to use this value, defaulting to 40.</action>
  <verify>.venv/bin/pytest tests/test_infra_33_timeout.py</verify>
  <done>Settings constructor correctly reads MIN_CATALOG_ITEMS from GCP/host environment before load_dotenv() is called, with a fallback default of 40.</done>
</task>

---
*Created: 2026-07-07*
