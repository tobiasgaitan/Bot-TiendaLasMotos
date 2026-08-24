"""ZSF forense logging para BOT-BUILD-CHINA-EVAL-090."""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("china_eval")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s [%(trace_id)s] %(message)s")
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    # File handler
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOG_DIR / "china_eval.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


def new_trace_id() -> str:
    return f"ce-{uuid.uuid4().hex[:16]}"


def log_event(
    trace_id: str,
    protocol: str,
    variant: int,
    provider: str,
    verdict: str,
    reason: str,
    request: dict | None = None,
    response: dict | None = None,
) -> None:
    logger = _get_logger()
    record = {
        "trace_id": trace_id,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "protocol": protocol,
        "variant": variant,
        "provider": provider,
        "verdict": verdict,
        "reason": reason,
        "request": request,
        "response": response,
    }
    extra = {"trace_id": trace_id}
    logger.info(json.dumps(record, ensure_ascii=False, default=str), extra=extra)
