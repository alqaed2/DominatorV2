from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str = "sqlite:///./dominator.db"
    API_PREFIX: str = "/v1"
    MAX_REQUEST_BYTES: int = 2_000_000  # 2MB payload guard for MVP

    # Gemini (optional in MVP; system falls back to deterministic templates)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Apify (optional)
    APIFY_API_KEY: str | None = None
    APIFY_TIKTOK_PROFILE_ACTOR: str | None = None  # e.g. actor id if you have it
    APIFY_TIKTOK_TREND_ACTOR: str | None = None

    # Rate limiting / safety
    MAX_REQUESTS_PER_IP_PER_MIN: int = 30
    MAX_CONCURRENT_JOBS: int = 2
    MODEL_TIMEOUT_SEC: int = 90

    # Feature flags
    ENABLE_LLM: bool = True
    ENABLE_APIFY: bool = True

    # TikTok integration (future)
    TIKTOK_CLIENT_KEY: str | None = None
    TIKTOK_CLIENT_SECRET: str | None = None

    # Governance defaults
    DEFAULT_SAFE_MODE: bool = True


settings = Settings()
