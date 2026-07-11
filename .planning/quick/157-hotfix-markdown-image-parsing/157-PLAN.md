---
task: 157
name: Hotfix Markdown Image Parsing
description: El enrutador de WhatsApp falló al interceptar la URL de la motocicleta Victory Advance R 125 debido a que la expresión regular en L1515 no capturó el string de Firebase Storage con query parameters extensos, enviando el Markdown crudo como texto.
---

# Quick Task 157: Hotfix Markdown Image Parsing

## Objective
Reemplazar 'image_pattern' por un patrón inmune a query parameters complejos en 'app/routers/whatsapp.py' y asegurar la purga limpia de grupos vacíos en 'images_found' para evitar que se envíe el Markdown crudo como texto.

## Tasks

<task type="auto">
  <name>Apply image pattern hotfix in whatsapp.py</name>
  <files>app/routers/whatsapp.py</files>
  <action>Reemplazar 'image_pattern' y purgar grupos vacíos en 'images_found' en el bloque L1512-L1530 de 'app/routers/whatsapp.py'.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>El patrón regex ha sido reemplazado y la suite de pruebas unitarias pasa exitosamente.</done>
</task>
