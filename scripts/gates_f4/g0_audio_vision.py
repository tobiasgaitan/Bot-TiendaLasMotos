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


def _make_silent_wav(duration_s: int = 1, sample_rate: int = 16000) -> bytes:
    """Genera un WAV mono silencioso de duración controlada (≤2 min)."""
    nchannels = 1
    sampwidth = 2
    nframes = duration_s * sample_rate
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(nchannels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00" * (nframes * sampwidth))
    return buf.getvalue()


def _make_jpeg_image() -> bytes:
    """Genera una imagen JPEG pequeña inline."""
    try:
        from PIL import Image
        img = Image.new("RGB", (128, 128), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return buf.getvalue()
    except Exception:
        # Fallback: tiny 1x1 JPEG (baseline, no secrets)
        return bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000ffdb004300"
            "080606070605080707070909080a0c140d0c0b0b0c1912130f"
            "141d1a1f1e1d1a1c1c20242e2720222c231c1c283728292c30"
            "31323434341f27393d383236343433ffdb0043010909090c0b"
            "0c180d0d1832211c2135353535353535353535353535353535"
            "35353535353535353535353535353535353535353535353535"
            "3535353535353535ffc0000b08000100010101011100ffc400"
            "1f000001050101010101010000000000000000010203040506"
            "0708090a0bffc400b510000201030302040305050404000001"
            "7d01020300041105122131410613516107227114328191a108"
            "2342b1c11552d1f02433627282090a161718191a2526272829"
            "2a3435363738393a434445464748494a535455565758595a63"
            "6465666768696a737475767778797a838485868788898a9293"
            "9495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9ba"
            "c2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7"
            "e8e9eaf1f2f3f4f5f6f7f8f9faffc4001f010003010101010101"
            "0101010000000000000102030405060708090a0bffc400b511"
            "00020102040403040705040400010277000102031104052131"
            "061241510761711322328108144291a1b1c109233352f01562"
            "72d10a162434e125f11718191a262728292a35363738393a43"
            "4445464748494a535455565758595a636465666768696a7374"
            "75767778797a82838485868788898a92939495969798999aa2"
            "a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9"
            "cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7"
            "f8f9faffda0008010100003f00fdfaf8a28a2803fffd9"
        )


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
    image_bytes = _make_jpeg_image()
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    facade = await get_shared_llm_client_async()
    response = await facade.aio.models.generate_content(
        model=os.environ["QWEN_PRIMARY_MODEL"],
        contents=["Describe la imagen en una sola palabra.", image_part],
        config=types.GenerateContentConfig(temperature=0.1),
    )
    text = (response.text or "").lower()
    # Esperamos que mencione color rojo o una descripción visual.
    ok = bool(text) and ("rojo" in text or "red" in text or "imagen" in text)
    return AVResult(
        case="image_jpeg_description",
        ok=ok,
        detail={
            "response": response.text,
            "image_bytes": len(image_bytes),
            "image_b64_len": len(base64.b64encode(image_bytes)),
        },
    )


async def _case_audio_description() -> AVResult:
    # 3 segundos de audio silencioso; ≤ 2 min (120 s) de cota.
    duration_s = 3
    audio_bytes = _make_silent_wav(duration_s=duration_s)
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
    image_bytes = _make_jpeg_image()
    audio_bytes = _make_silent_wav(duration_s=2)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
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
