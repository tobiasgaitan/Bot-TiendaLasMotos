"""
G0-GEMINI-35: smoke real de modelos Gemini candidatos en Vertex AI.
Orden de intento:
  1. gemini-3.5-flash-lite
  2. gemini-3.5-flash
  3. gemini-3.1-pro-preview
  4. gemini-3.6-flash
200 OK + texto no vacío en el primero -> verde y dictado.
Cualquier otro resultado -> STOP y evidencia.
"""
from __future__ import annotations

import asyncio
import os
import sys

from google import genai
from google.genai import types


PROJECT = "tiendalasmotos"
LOCATION = "us-central1"
CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.6-flash",
]


async def smoke(model_id: str) -> dict:
    result = {"model": model_id, "status": None, "text": None, "error": None}
    try:
        client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
        response = await client.aio.models.generate_content(
            model=model_id,
            contents="Responde 'OK' y nada más.",
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=10),
        )
        result["status"] = 200
        result["text"] = response.text
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


async def main() -> int:
    print(f"G0-GEMINI-35 smoke en {PROJECT}/{LOCATION}")
    for model_id in CANDIDATES:
        print(f"\nIntentando {model_id}...")
        result = await smoke(model_id)
        print(f"  status={result['status']} text={result['text']!r} error={result['error']}")
        if result["status"] == 200 and result["text"]:
            print(f"\n✅ VERDE: {model_id} responde 200 OK con texto.")
            print(f"GEMINI_MODEL_ID={model_id}")
            return 0
    print("\n❌ ROJO: ningún modelo candidato respondió 200 OK con texto.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
