# config.py
from __future__ import annotations
import os
from typing import Optional


def _read_secret_file(name: str) -> Optional[str]:
    """
    Render Secret Files are mounted at /etc/secrets/<FILENAME>
    """
    path = f"/etc/secrets/{name}"
    try:
        if os.path.exists(path):
            v = open(path, "r", encoding="utf-8").read().strip()
            return v or None
    except Exception:
        return None
    return None


def _getenv(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name, None)
    if v is not None and str(v).strip() != "":
        return str(v).strip()
    return default


def _getsecret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read from Environment Variables first, then Secret Files.
    """
    v = _getenv(name, None)
    if v:
        return v
    sf = _read_secret_file(name)
    if sf:
        return sf
    return default


def _getint(name: str, default: int) -> int:
    v = _getenv(name)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def _getbool(name: str, default: bool = False) -> bool:
    v = _getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # Core
    ASYNC_ENABLED = _getbool("ASYNC_ENABLED", True)
    LOG_LEVEL = _getenv("LOG_LEVEL", "INFO") or "INFO"

    # Limits
    MAX_CONCURRENT_JOBS = _getint("MAX_CONCURRENT_JOBS", 1)
    MAX_QUEUE_BACKLOG = _getint("MAX_QUEUE_BACKLOG", 60)
    MAX_REQUESTS_PER_IP_PER_MIN = _getint("MAX_REQUESTS_PER_IP_PER_MIN", 60)
    MODEL_TIMEOUT_SEC = _getint("MODEL_TIMEOUT_SEC", 60)

    # Worker tick
    WORKER_TICK_TOKEN = _getsecret("WORKER_TICK_TOKEN", "")

    # Gemini
    GEMINI_API_KEY = _getsecret("GEMINI_API_KEY", "")
    GEMINI_MODEL = _getenv("GEMINI_MODEL", "gemini-flash-latest") or "gemini-flash-latest"

    # Optional Apify
    APIFY_API_KEY = _getsecret("APIFY_API_KEY", "")
    APIFY_TOKEN = _getsecret("APIFY_TOKEN", "")


settings = Settings()
