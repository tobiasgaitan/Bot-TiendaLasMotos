#!/usr/bin/env python3
"""
Media helpers para tráfico sintético F4.5 (OPCIÓN-A).
Genera PNG 64x64 y WAV <=2s sin dependencias externas y los sube al canal
WhatsApp beta vía POST /{phone_number_id}/media.
"""
from __future__ import annotations

import io
import math
import os
import struct
import subprocess
import wave
from pathlib import Path
from typing import Optional

import httpx


META_API_VERSION = "v18.0"


def _load_secret(name: str, project: str = "tiendalasmotos") -> str:
    return (
        subprocess.check_output(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                "--secret",
                name,
                "--project",
                project,
            ],
            text=True,
        )
        .strip()
    )


def load_whatsapp_token() -> str:
    token = os.getenv("WHATSAPP_TOKEN")
    if not token:
        try:
            token = _load_secret("WHATSAPP_TOKEN")
        except Exception as exc:
            raise RuntimeError(
                "WHATSAPP_TOKEN no está en env ni pudo cargarse desde Secret Manager"
            ) from exc
    return token


def make_png_image(width: int = 64, height: int = 64) -> bytes:
    """Genera una imagen PNG RGB 64x64 sin dependencias externas."""
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    idat = zlib.compress(raw)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def make_wav(duration_s: int = 1, sample_rate: int = 16000, tone: bool = True) -> bytes:
    """Genera un WAV mono <=2s (tono 440Hz o silencio)."""
    if duration_s > 2:
        duration_s = 2
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
                struct.pack(
                    "<h",
                    int(32767 * 0.5 * math.sin(2 * math.pi * 440 * t / sample_rate)),
                )
                for t in range(nframes)
            )
        else:
            data = b"\x00" * (nframes * sampwidth)
        w.writeframes(data)
    return buf.getvalue()


def upload_media(
    phone_number_id: str,
    token: str,
    data: bytes,
    mime_type: str,
    filename: str,
    timeout: float = 60.0,
) -> str:
    """Sube un archivo a Meta y retorna el media_id."""
    url = f"https://graph.facebook.com/{META_API_VERSION}/{phone_number_id}/media"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, io.BytesIO(data), mime_type)},
        )
    resp.raise_for_status()
    body = resp.json()
    media_id = body.get("id")
    if not media_id:
        raise RuntimeError(f"Meta no retornó media_id: {body}")
    return media_id


def upload_image_media(phone_number_id: str, token: str, timeout: float = 60.0) -> str:
    return upload_media(
        phone_number_id,
        token,
        make_png_image(),
        "image/png",
        "synthetic_moto.png",
        timeout,
    )


def make_aac_bytes(duration_s: int = 1, sample_rate: int = 16000) -> bytes:
    """Genera un AAC (.m4a) desde un WAV usando afconvert (macOS) o ffmpeg."""
    import shutil
    import tempfile

    wav_bytes = make_wav(duration_s=duration_s, sample_rate=sample_rate, tone=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "tone.wav"
        m4a_path = Path(tmpdir) / "tone.m4a"
        wav_path.write_bytes(wav_bytes)

        if shutil.which("afconvert"):
            subprocess.run(
                ["afconvert", str(wav_path), str(m4a_path), "-f", "m4af", "-d", "aac"],
                check=True,
                capture_output=True,
            )
        elif shutil.which("ffmpeg"):
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "aac", str(m4a_path)],
                check=True,
                capture_output=True,
            )
        else:
            raise RuntimeError("Se requiere afconvert (macOS) o ffmpeg para generar audio AAC")

        return m4a_path.read_bytes()


def upload_audio_media(phone_number_id: str, token: str, timeout: float = 60.0) -> str:
    return upload_media(
        phone_number_id,
        token,
        make_aac_bytes(duration_s=1),
        "audio/mp4",
        "synthetic_audio.m4a",
        timeout,
    )


if __name__ == "__main__":
    import os

    phone_id = os.getenv("BETA_PHONE_NUMBER_ID", "1021779847693778")
    tok = load_whatsapp_token()
    print("Subiendo imagen...")
    img_id = upload_image_media(phone_id, tok)
    print(f"image media_id={img_id}")
    print("Subiendo audio...")
    aud_id = upload_audio_media(phone_id, tok)
    print(f"audio media_id={aud_id}")
