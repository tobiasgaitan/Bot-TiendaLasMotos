# Estado del Proyecto - Bot-TiendaLasMotos

Versión: v10.52.1 | Hito: O1 — Erradicación catalog_items + agent-cli publish NO-OP | Coherence Score: 1.000 (673/673 Tests PASSED vía `npx agent-cli eval`)

### Current Position
**Phase:** O1 (Milestone patch v10.52.1) — Erradicación de la colección huérfana `catalog_items` de Firestore prod + agent-cli publish NO-OP — CERRADA (Success)
**Status:** Complete — Ejecución certificada contra el runbook consolidado:
  - Backup bloqueante en `attic/backup_catalog_items_2026-08-05.json` (4 docs: mrx-150, nkd-125, sport-100, victory-black) verificado antes del borrado.
  - `catalog_items` eliminada de producción; re-listado post-borrado: 0 docs.
  - Seed script archivado (`git mv scripts/seed_catalog.py attic/seed_catalog.py`).
  - Documentos `FIRESTORE_CATALOG_SYNC.md` y `CATALOG_SEEDING_GUIDE.md` actualizados con cabecera de erradicación y SSOT `pagina/catalogo/items`.
  - `scripts/buscar_y_destruir.py` marca `catalog_items` como ERRADICADA en listado cosmético.
  - `.gitignore` añade `.opencode/` (precedente .vscode/.idea) sin commitear ni eliminar el archivo local.
  - `agent-cli` publish NO-OP: sin cambios en `package.json`/`bin/agent-cli.js` desde el commit-1.0.6 (`273c063`); no se publicó ni se hizo bump.
  - 0 cambios a `app/`, `catalog_service.py`, `normalize_imagen_url.py`, `pagina/catalogo/items`, `juan_pablo_personality`.
  - Denominador canónico INVARIANTE 673 = 668 tests/ + 5 scripts/; 673/673 PASSED; 0 failed; 0 skipped. Coherence 1.000 — DEPLOY AUTHORIZED (beta, push diferido).

**Previous:** AUD-FP-AUTO-007 (v10.52.0) — Regla determinista `forma_pago="Crédito"` en aceptación PASO 4 + T3 deduplicación de `save_message` — CERRADA (Success)
**Next:** Push autorizado a beta + tag v10.52.1 (o deploy según orden).

---
*Last updated: 2026-08-05*
