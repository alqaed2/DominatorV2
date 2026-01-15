# config.py
from __future__ import annotations

import os
from typing import Optional

from pydantic_settings import BaseSettings


def _normalize_db_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _read_secret_file(name: str) -> Optional[str]:
    # Render Secret Files:
    #  - /etc/secrets/<filename>
    #  - app root: ./<filename>
    candidates = [
        os.path.join("/etc/secrets", name),
        os.path.join(os.getcwd(), name),
    ]
    for p in candidates:
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    v = f.read().strip()
                    if v:
                        return v
        except Exception:
            pass
    return None


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    # Preference order:
    # 1) Environment Variables (best performance)
    # 2) Render Secret Files (best immunity)
    v = os.getenv(name)
    if v is not None:
        v = v.strip()
        if v:
            return v
    v2 = _read_secret_file(name)
    if v2:
        return v2
    return default


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    LOG_LEVEL: str = "INFO"

    MAX_REQUESTS_PER_IP_PER_MIN: int = 60
    MAX_QUEUE_BACKLOG: int = 60
    MAX_CONCURRENT_JOBS: int = 2
    MODEL_TIMEOUT_SEC: int = 45

    # Hybrid behaviour
    ASYNC_ENABLED: bool = True

    WORKER_TICK_TOKEN: str = ""

    APIFY_API_KEY: str = ""

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1beta"

    ALLOW_ADMIN_QUERY_TOKEN: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

settings.DATABASE_URL = _normalize_db_url(settings.DATABASE_URL or os.getenv("DATABASE_URL", ""))

if not settings.GEMINI_API_KEY:
    settings.GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "") or ""
if not settings.APIFY_API_KEY:
    settings.APIFY_API_KEY = get_secret("APIFY_API_KEY", "") or ""
if not settings.WORKER_TICK_TOKEN:
    settings.WORKER_TICK_TOKEN = get_secret("WORKER_TICK_TOKEN", "") or ""

settings.GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or settings.GEMINI_MODEL or "gemini-flash-latest").strip()
