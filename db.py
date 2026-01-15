# db.py
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(getattr(settings, "DB_POOL_SIZE", 3) or 3),
    max_overflow=int(getattr(settings, "DB_MAX_OVERFLOW", 2) or 2),
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from models import Base  # noqa

    Base.metadata.create_all(bind=engine)
