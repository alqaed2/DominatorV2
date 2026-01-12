import os


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


class Settings:
    # Core runtime
    LOG_LEVEL: str = _getenv("LOG_LEVEL", "INFO") or "INFO"

    # Database
    DATABASE_URL: str = _getenv("DATABASE_URL", "sqlite:///./local.db") or "sqlite:///./local.db"

    # Queue / Worker
    REDIS_URL: str | None = _getenv("REDIS_URL")
    QUEUE_NAME: str = _getenv("QUEUE_NAME", "dominator") or "dominator"

    # Async mode:
    # - If True and REDIS+Worker exists -> enqueue
    # - If True and NO Worker -> remain queued and processed by /internal/worker-tick
    ASYNC_ENABLED: bool = _getbool("ASYNC_ENABLED", True)

    # Workerless tick security (REQUIRED for free mode)
    WORKER_TICK_TOKEN: str | None = _getenv("WORKER_TICK_TOKEN")

    # Load guards
    MAX_CONCURRENT_JOBS: int = _getint("MAX_CONCURRENT_JOBS", 2)   # running only
    MAX_QUEUE_BACKLOG: int = _getint("MAX_QUEUE_BACKLOG", 30)      # queued backlog cap
    MAX_REQUESTS_PER_IP_PER_MIN: int = _getint("MAX_REQUESTS_PER_IP_PER_MIN", 30)

    # Model routing
    GEMINI_API_KEY: str | None = _getenv("GEMINI_API_KEY") or _getenv("GOOGLE_API_KEY")
    GEMINI_MODEL: str = _getenv("GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash"
    NEBULA_MODELS: str = _getenv(
        "NEBULA_MODELS",
        "gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash,gemini-1.5-pro",
    ) or "gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash,gemini-1.5-pro"
    MODEL_TIMEOUT_SEC: int = _getint("MODEL_TIMEOUT_SEC", 45)

    # Trends
    TRENDS_PROVIDER: str = _getenv("TRENDS_PROVIDER", "mock") or "mock"
    APIFY_TOKEN: str | None = _getenv("APIFY_TOKEN")
    APIFY_TRENDS_ENDPOINT: str | None = _getenv("APIFY_TRENDS_ENDPOINT")


settings = Settings()
