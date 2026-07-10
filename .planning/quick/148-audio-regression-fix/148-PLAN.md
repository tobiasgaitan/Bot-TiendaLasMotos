---
task: 148
name: Audio Regression Fix
description: Fallo de regresión en el procesamiento de audios en whatsapp.py debido a un payload vacío en last_bot_question al invocar generate_and_update_summary, rompiendo la persistencia semántica y causando colisiones en hilos que derivan en respuestas HTTP 503.
---

# Quick Task 148: Audio Regression Fix

## Objective
Corregir la regresión en el procesamiento de mensajes de audio en `app/routers/whatsapp.py` mediante la extracción e inyección síncrona de la última pregunta del bot (`last_bot_question`) en `generate_and_update_summary`, y crear un test unitario estricto en `tests/test_audio_regression.py` que simule un payload binario completo para garantizar que no se propaguen cadenas vacías y que retorne HTTP 200 OK de forma síncrona.

## Tasks

<task type="auto">
  <name>Correct last_bot_question injection in audio block of app/routers/whatsapp.py</name>
  <files>[app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py)</files>
  <action>Extraer el last_bot_question de la historia de conversación en el bloque elif msg_type == "audio" e inyectarlo en la llamada generate_and_update_summary, en lugar de pasar una cadena vacía.</action>
  <verify>Revisar visualmente el archivo modificado y verificar que coincida con el bloque de texto.</verify>
  <done>La última pregunta del bot se extrae del historial e inyecta correctamente en generate_and_update_summary.</done>
</task>

<task type="auto">
  <name>Create strict unit test in tests/test_audio_regression.py</name>
  <files>[tests/test_audio_regression.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_audio_regression.py)</files>
  <action>Crear el archivo tests/test_audio_regression.py que simule la recepción de un webhook con un mensaje de audio, mockeando la descarga de audio y la transcripción, asegurando que last_bot_question se extraiga e inyecte correctamente y que el endpoint retorne un 200 OK de forma síncrona.</action>
  <verify>npx @tobiasgaitan/agent-cli eval</verify>
  <done>El nuevo test de regresión de audio pasa exitosamente y el total de test suite pasa con score 1.000.</done>
</task>
