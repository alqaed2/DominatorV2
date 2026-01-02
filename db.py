import os
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

Base = declarative_base()

def _pick_postgres_driver() -> str:
    """
    Prefer psycopg (v3). Fallback to psycopg2 if present.
    Fail fast with a clear message if neither is installed.
    """
    try:
        import psycopg  # noqa: F401
        return "psycopg"
    except Exception:
        pass

    try:
        import psycopg2  # noqa: F401
        return "psycopg2"
    except Exception:
        pass

    raise RuntimeError(
        "No Postgres driver installed. Install one of:\n"
        "- psycopg[binary] (recommended)\n"
        "- psycopg2-binary"
    )

def _normalize_db_url(raw: str) -> str:
    if not raw:
        raise RuntimeError("DATABASE_URL is missing")

    # Render may provide postgres:// which SQLAlchemy expects as postgresql://
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql://", 1)

    # SQLite remains supported (dev)
    if raw.startswith("sqlite"):
        return raw

    # Postgres: enforce a driver that is actually installed
    if raw.startswith("postgresql"):
        driver = _pick_postgres_driver()
        url = make_url(raw)

        # Force drivername to match installed driver
        url = url.set(drivername=f"postgresql+{driver}")
        return str(url)

    return raw

_db_url = _normalize_db_url(settings.DATABASE_URL)

connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(
    _db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

def init_db():
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
