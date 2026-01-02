import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from config import settings
from models import Base


def _normalize_db_url(url: str) -> str:
    """
    Render/Postgres often provides postgres://... which SQLAlchemy treats as psycopg2 by default.
    We normalize to postgresql+psycopg://... to use psycopg3 (psycopg[binary]).
    """
    if not url:
        return url

    # Render commonly uses postgres://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    # If it's a postgres URL without an explicit driver, force psycopg3
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


_db_url = _normalize_db_url(settings.DATABASE_URL)

connect_args = {}
if _db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    _db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
