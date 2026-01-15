from __future__ import annotations

import os
from typing import Optional


def _read_secret_file(name: str) -> Optional[str]:
    """
    Read secrets from Render Secret Files:
      - /etc/secrets/<filename>
    Also supports local/testing:
      - ./<filename>
    """
    for p in (os.path.join("/etc/secrets", name), os.path.join(os.getcwd(), name)):
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    v = (f.read() or "").strip()
                    if v:
                        return v
        except Exception:
            continue
    return None


def get_secret(name: str, default: Optional[str] = None) -> tuple[Optional[str], str]:
    """Return (value, source): env | secret_file | default"""
    v = os.getenv(name)
    if v is not None and v.strip():
        return v.strip(), "env"
    v2 = _read_secret_file(name)
    if v2:
        return v2, "secret_file"
    return default, "default"


def _getenv(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


def _getint(key: str, default: int) -> int:
    v = _getenv(key)
    try:
        return int(v) if v is not None else default
    except Exception:
        return default


def _getbool(key: str, default: bool) -> bool:
    v = _getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _normalize_db_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Settings:
    LOG_LEVEL: str = _getenv("LOG_LEVEL", "INFO") or "INFO"

    DATABASE_URL: str = _normalize_db_url(
        _getenv("DATABASE_URL", "sqlite:///./local.db") or "sqlite:///./local.db"
    )

    # Threads-based async inside web process
    ASYNC_ENABLED: bool = _getbool("ASYNC_ENABLED", True)
    HYBRID_FASTPATH: bool = _getbool("HYBRID_FASTPATH", True)

    # Load guards
    MAX_CONCURRENT_JOBS: int = _getint("MAX_CONCURRENT_JOBS", 2)
    MAX_QUEUE_BACKLOG: int = _getint("MAX_QUEUE_BACKLOG", 30)
    MAX_REQUESTS_PER_IP_PER_MIN: int = _getint("MAX_REQUESTS_PER_IP_PER_MIN", 30)

    MODEL_TIMEOUT_SEC: int = _getint("MODEL_TIMEOUT_SEC", 25)

    # Worker tick security (GitHub Actions)
    WORKER_TICK_TOKEN: str | None = None

    # Gemini
    GEMINI_API_KEY: str | None = None
    GEMINI_API_KEY_SOURCE: str = "missing"
    GEMINI_MODEL: str = _getenv("GEMINI_MODEL", "gemini-flash-latest") or "gemini-flash-latest"

    # Nebula failover list (first = preferred)
    NEBULA_MODELS: str = _getenv(
        "NEBULA_MODELS",
        "gemini-flash-latest,gemini-2.0-flash,gemini-1.5-flash,gemini-1.5-pro",
    ) or "gemini-flash-latest,gemini-2.0-flash,gemini-1.5-flash,gemini-1.5-pro"

    # Trends
    TRENDS_PROVIDER: str = _getenv("TRENDS_PROVIDER", "static") or "static"
    APIFY_TOKEN: str | None = None
    APIFY_TRENDS_ENDPOINT: str | None = _getenv("APIFY_TRENDS_ENDPOINT")


settings = Settings()

# Resolve tick token (env -> secret file)
v_tick, _ = get_secret("WORKER_TICK_TOKEN", _getenv("WORKER_TICK_TOKEN"))
settings.WORKER_TICK_TOKEN = (v_tick or "").strip() or None

# Resolve Gemini key (env -> secret file), allow GOOGLE_API_KEY fallback
v_key, src = get_secret("GEMINI_API_KEY", _getenv("GEMINI_API_KEY"))
if not v_key:
    v_key, src = get_secret("GOOGLE_API_KEY", _getenv("GOOGLE_API_KEY"))

settings.GEMINI_API_KEY = (v_key or "").strip() or None
settings.GEMINI_API_KEY_SOURCE = src if settings.GEMINI_API_KEY else "missing"

# Optional Apify
v_ap, _ = get_secret("APIFY_TOKEN", _getenv("APIFY_TOKEN"))
settings.APIFY_TOKEN = (v_ap or "").strip() or None
