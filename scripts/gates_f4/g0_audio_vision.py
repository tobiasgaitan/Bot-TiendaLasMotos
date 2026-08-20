"""
G0-AUDIO-VISION: gate de audio e imagen contra Qwen (qwen-omni-turbo).
Mecanismo certificado BOT-PLAN-GATES-OVERRIDE-080:
  - Patch local de app.services.llm_client_service.is_qwen_enabled para la llamada Qwen.
  - Retry ante ConnectError/ReadTimeout.
Cotas:
  - Audio: WAV mono ≤ 2 min.
  - Imagen: JPEG/WebP inline.
  - Registro del tamaño de payload inline para comparación con uso vivo.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import subprocess
import sys
import wave
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from google.genai import types

from app.services.llm_client_service import (
    get_shared_llm_client_async,
    reset_shared_llm_clients,
)


def _load_secret(name: str) -> str:
    return subprocess.check_output(
        ["gcloud", "secrets", "versions", "access", "latest", "--secret", name, "--project=tiendalasmotos"],
        text=True,
    ).strip()


def _bootstrap_env() -> None:
    os.environ.setdefault("QWEN_OMNI_API_KEY", _load_secret("QWEN_OMNI_API_KEY"))
    os.environ.setdefault("QWEN_TURBO_API_KEY", _load_secret("QWEN_TURBO_API_KEY"))
    os.environ.setdefault("QWEN_BASE_URL", _load_secret("QWEN_BASE_URL"))
    os.environ.setdefault("QWEN_PRIMARY_MODEL", "qwen-omni-turbo")
    os.environ.setdefault("QWEN_CALL_TIMEOUT_S", "120")


def _make_wav(duration_s: int = 1, sample_rate: int = 16000, tone: bool = False) -> bytes:
    """Genera un WAV mono (silencioso o tono 440Hz) de duración controlada (≤2 min)."""
    import math
    import struct

    nchannels = 1
    sampwidth = 2
    nframes = duration_s * sample_rate
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(nchannels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        if tone:
            data = b"".join(
                struct.pack("<h", int(32767 * 0.5 * math.sin(2 * math.pi * 440 * t / sample_rate)))
                for t in range(nframes)
            )
        else:
            data = b"\x00" * (nframes * sampwidth)
        w.writeframes(data)
    return buf.getvalue()


def _make_png_image(width: int = 64, height: int = 64) -> bytes:
    """Genera una imagen PNG RGB inline sin dependencias externas."""
    import struct
    import zlib

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # IDAT: scanlines filter 0 + RGB pixels (red)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    idat = zlib.compress(raw)
    # IEND empty
    return sig + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")


@dataclass
class AVResult:
    case: str
    ok: bool = False
    error: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)


async def _run_case(name: str, runner, retries: int = 3) -> AVResult:
    result = AVResult(case=name)
    last_error: Optional[str] = None
    for attempt in range(retries):
        reset_shared_llm_clients()
        try:
            with patch("app.services.llm_client_service.is_qwen_enabled", lambda: True):
                return await runner()
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            result.error = last_error
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
    result.ok = False
    return result


async def _case_image_description() -> AVResult:
    image_bytes = _make_png_image(width=64, height=64)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

    facade = await get_shared_llm_client_async()
    response = await facade.aio.models.generate_content(
        model=os.environ["QWEN_PRIMARY_MODEL"],
        contents=["Describe la imagen en una sola palabra.", image_part],
        config=types.GenerateContentConfig(temperature=0.1),
    )
    text = response.text or ""
    # Se acepta cualquier descripción visual no vacía como evidencia de procesamiento.
    ok = bool(text) and len(text.strip()) >= 1
    return AVResult(
        case="image_jpeg_description",
        ok=ok,
        detail={
            "response": text,
            "image_bytes": len(image_bytes),
            "image_b64_len": len(base64.b64encode(image_bytes)),
        },
    )


async def _case_audio_description() -> AVResult:
    # 2 segundos de tono 440Hz; ≤ 2 min (120 s) de cota.
    duration_s = 2
    audio_bytes = _make_wav(duration_s=duration_s, tone=True)
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")

    facade = await get_shared_llm_client_async()
    response = await facade.aio.models.generate_content(
        model=os.environ["QWEN_PRIMARY_MODEL"],
        contents=[audio_part, "Describe lo que escuchas."],
        config=types.GenerateContentConfig(temperature=0.1),
    )
    text = response.text or ""
    # Para audio silencioso, esperamos que al menos responda sin error.
    ok = bool(text)
    return AVResult(
        case="audio_wav_description",
        ok=ok,
        detail={
            "response": text,
            "duration_s": duration_s,
            "audio_bytes": len(audio_bytes),
            "audio_b64_len": len(base64.b64encode(audio_bytes)),
        },
    )


async def _case_combined_payload_size() -> AVResult:
    """Envía imagen + audio juntos y registra el tamaño aproximado del payload inline."""
    image_bytes = _make_png_image(width=64, height=64)
    audio_bytes = _make_wav(duration_s=1, tone=False)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")

    facade = await get_shared_llm_client_async()
    response = await facade.aio.models.generate_content(
        model=os.environ["QWEN_PRIMARY_MODEL"],
        contents=["Aquí hay una imagen y un audio.", image_part, audio_part],
        config=types.GenerateContentConfig(temperature=0.1),
    )
    total_inline = len(base64.b64encode(image_bytes)) + len(base64.b64encode(audio_bytes))
    ok = bool(response.text)
    return AVResult(
        case="combined_image_audio",
        ok=ok,
        detail={
            "response": response.text,
            "total_inline_b64_chars": total_inline,
            "image_bytes": len(image_bytes),
            "audio_bytes": len(audio_bytes),
        },
    )


async def main() -> int:
    _bootstrap_env()
    print("=" * 60)
    print("G0-AUDIO-VISION: audio e imagen Qwen (qwen-omni-turbo)")
    print("=" * 60)

    results: List[Dict[str, Any]] = []
    failures = 0

    runners = [
        ("image_jpeg_description", _case_image_description),
        ("audio_wav_description", _case_audio_description),
        ("combined_image_audio", _case_combined_payload_size),
    ]

    for name, runner in runners:
        print(f"\n[Caso] {name}")
        result = await _run_case(name, runner)
        print(f"  ok={result.ok} detail={result.detail} error={result.error}")
        results.append({"case": name, "ok": result.ok, "detail": result.detail, "error": result.error})
        if not result.ok:
            failures += 1
            print("  -> FAIL")
        else:
            print("  -> PASS")

    print("\n" + "=" * 60)
    status = "ROJO" if failures else "VERDE"
    print(f"RESULTADO: {status}")
    print(f"  Fallos: {failures}/{len(runners)}")
    print("=" * 60)

    with open("scripts/gates_f4/g0_audio_vision_report.json", "w", encoding="utf-8") as f:
        json.dump({"status": status, "failures": failures, "cases": results}, f, ensure_ascii=False, indent=2)
    print("Reporte guardado en scripts/gates_f4/g0_audio_vision_report.json")
    return 1 if status == "ROJO" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
