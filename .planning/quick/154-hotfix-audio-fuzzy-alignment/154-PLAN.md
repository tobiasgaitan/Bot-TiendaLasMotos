---
task: 154
name: hotfix_audio_fuzzy_alignment
description: Falta de sanitización y alineación fonética fuzzy sobre el string de salida de transcription en el bloque audio de app/routers/whatsapp.py, provocando que variaciones tipográficas aceptadas en texto (ej. 'rader') fallen el PCC/Filtro del Juez en formato nota de voz.
---

# Quick Task 154: hotfix_audio_fuzzy_alignment

## Objective
Sanitize and align phonetic fuzzy terms in the transcription of the audio webhook block within `app/routers/whatsapp.py` using `CatalogService`'s phonetic matching/homophone/fuzzy rules before inference and judge audit. In addition, inject a characterization test in `tests/test_audio_regression.py` that verifies phonetic normalization of 'rader' to 'raider' under an audio message and assert it does not cause handoff or fail judge validation.

## Tasks

<task type="auto">
  <name>Implement normalize_transcription in CatalogService</name>
  <files>app/services/catalog_service.py</files>
  <action>Add normalize_transcription method to CatalogService that sanitizes input and aligns phonetic/fuzzy variants of catalog tokens (e.g. 'rader' -> 'raider', 'rayder' -> 'raider') by checking spelling_map, stop_words, and SequenceMatcher logic.</action>
  <verify>uv run pytest tests/test_catalog_fuzzy.py</verify>
  <done>Successful execution of catalog fuzzy unit tests.</done>
</task>

<task type="auto">
  <name>Integrate normalize_transcription in whatsapp.py audio block</name>
  <files>app/routers/whatsapp.py</files>
  <action>Call catalog_service.normalize_transcription(transcription) inside the elif msg_type == "audio" block, updating the transcription string before calling cerebro_ia.pensar_respuesta and judge_service.analyze_response.</action>
  <verify>uv run pytest tests/test_audio_regression.py</verify>
  <done>Successful execution of audio webhook regression tests.</done>
</task>

<task type="auto">
  <name>Add phonetic audio regression test</name>
  <files>tests/test_audio_regression.py</files>
  <action>Add a characterization test case that forces raw transcription of 'rader' to be aligned to 'raider', and assert that judge approval is True and human handoff flag is not activated.</action>
  <verify>npx agent-cli eval</verify>
  <done>Suite of 234/234 tests passing with zero failures.</done>
</task>

---
*Created: 2026-07-10*
