# Plan de Tareas - Hotfix Saludo Inicial (BOT-UI-GREETING-088)

Este plan de tareas describe las modificaciones necesarias en `app/routers/whatsapp.py` para asegurar que el bot Juan Pablo presente un saludo inicial de bienvenida en el primer mensaje de la sesión, independientemente de si existe un interés previo (`moto_interest`) o del estado de la base de datos (por ejemplo, en prospectos precargados o campañas masivas).

## Objetivos
1. Asegurar que `skip_greeting` sea `False` si es el primer mensaje del usuario en la sesión (evaluado contando los mensajes del usuario en el historial).
2. Implementar la inyección síncrona obligatoria de un saludo comercial estándar de Juan Pablo en `response_text` cuando `skip_greeting` es `False` y la respuesta del modelo no contiene un saludo explícito.
3. Asegurar que no se alteren el "Catalog Lock" ni las reglas de visuales y de formato de precios del "PCC Pro".

## Tareas

<task type="auto">
  <name>Modificar app/routers/whatsapp.py para habilitar e inyectar el saludo inicial</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>
    - Modificar el cálculo de `skip_greeting` para usar el conteo de mensajes del usuario (`role == "user"`) en lugar de la longitud total del historial.
    - Implementar la inyección síncrona obligatoria del saludo estándar al final de la inferencia de la IA cuando `not skip_greeting` y no exista un saludo previo en la respuesta.
  </action>
  <verify>
    - Ejecutar pruebas unitarias locales para validar el comportamiento del webhook y de la inyección de saludo.
  </verify>
  <done>
    - El primer mensaje de una nueva sesión (vacía) contiene el saludo comercial estándar de Juan Pablo sin romper las aserciones de formato de catálogo ni precios.
  </done>
</task>

<task type="auto">
  <name>Crear prueba unitaria para verificar el saludo inicial y validar coherencia</name>
  <files>
    <file>tests/test_saludo_inicial.py</file>
  </files>
  <action>
    - Crear un nuevo archivo de prueba `tests/test_saludo_inicial.py` que valide que al recibir el primer mensaje en una sesión nueva, la respuesta contenga el saludo estándar de Juan Pablo.
    - Asegurar que si existe `moto_interest` en la base de datos (prospect_data), aun así se envíe el saludo respetuoso de bienvenida.
  </action>
  <verify>
    - Ejecutar `.venv/bin/pytest tests/test_saludo_inicial.py`
    - Ejecutar `npx agent-cli eval`
  </verify>
  <done>
    - La prueba unitaria pasa exitosamente y el score de coherencia sigue siendo 1.000.
  </done>
</task>
