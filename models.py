# models.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from sqlalchemy.dialects.postgresql import JSONB as _JSON
except Exception:
    from sqlalchemy import JSON as _JSON  # type: ignore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    status: Mapped[str] = mapped_column(String(16), index=True, default="queued", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    request: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)

    pack_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("packs.id"), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    pack: Mapped[Optional["Pack"]] = relationship("Pack", back_populates="job", foreign_keys=[pack_id], uselist=False)


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)

    job_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("jobs.id"), index=True, nullable=True)

    mode: Mapped[str] = mapped_column(String(32), default="niche", nullable=False)
    input_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="ar", nullable=False)
    tone: Mapped[str] = mapped_column(String(32), default="Authority", nullable=False)
    platforms: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=list, nullable=False)

    genes: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)
    assets: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)
    visual: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)
    dominance: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)
    sources: Mapped[Dict[str, Any]] = mapped_column(_JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    job: Mapped[Optional[Job]] = relationship("Job", back_populates="pack", foreign_keys=[job_id], uselist=False)


Index("ix_packs_job_id", Pack.job_id)
