---
task: 009
name: Refactor Agent CLI Identity
description: Sincronizar identidad a @tobiasgaitan/agent-cli v1.0.2 y cargar versión dinámicamente desde package.json.
---

# Quick Task 009: Refactor Agent CLI Identity

## Objective
Sincronizar la identidad del CLI a `@tobiasgaitan/agent-cli v1.0.2`, eliminando referencias estáticas a `@tiendalasmotos` y cargando la versión dinámicamente desde el `package.json` raíz.

## Tasks

<task type="auto">
  <name>Update package.json version</name>
  <files>["package.json"]</files>
  <action>Actualizar el campo version a "1.0.2" en package.json.</action>
  <verify>cat package.json | grep version</verify>
  <done>La versión en package.json es "1.0.2".</done>
</task>

<task type="auto">
  <name>Refactor bin/agent-cli.js</name>
  <files>["bin/agent-cli.js"]</files>
  <action>Modificar bin/agent-cli.js para:
1. Requerir package.json dinámicamente.
2. Definir VERSION y PACKAGE_NAME desde el archivo requerido.
3. Reemplazar todas las ocurrencias de @tiendalasmotos por el scope correcto o referencias dinámicas.</action>
  <verify>./bin/agent-cli.js --version</verify>
  <done>El comando devuelve "@tobiasgaitan/agent-cli v1.0.2".</done>
</task>

---
*Created: 2026-05-02*
