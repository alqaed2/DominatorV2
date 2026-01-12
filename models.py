from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from db import Base


def _now() -> datetime:
    return datetime.utcnow()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|running|failed|done
    progress: Mapped[float] = mapped_column(Float, default=0.0)

    request: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    pack_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("packs.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pack = relationship("Pack", back_populates="job", lazy="joined")
    events = relationship("Event", back_populates="job", cascade="all, delete-orphan")
    score = relationship("Score", back_populates="job", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )


class Pack(Base):
    __tablename__ = "packs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)

    mode: Mapped[str] = mapped_column(String(10), default="niche")  # niche|url
    input_value: Mapped[str] = mapped_column(Text, default="")

    language: Mapped[str] = mapped_column(String(10), default="ar")
    platforms: Mapped[list] = mapped_column(JSON, default=list)
    tone: Mapped[str] = mapped_column(String(50), default="authority")

    genes: Mapped[dict] = mapped_column(JSON, default=dict)
    assets: Mapped[dict] = mapped_column(JSON, default=dict)
    visual: Mapped[dict] = mapped_column(JSON, default=dict)

    dominance: Mapped[dict] = mapped_column(JSON, default=dict)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job = relationship("Job", back_populates="pack", uselist=False)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id"), index=True)

    type: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job = relationship("Job", back_populates="events")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id"), unique=True)

    score: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(String(30), default="revise")  # publish|revise|regenerate
    version: Mapped[str] = mapped_column(String(20), default="v1")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job = relationship("Job", back_populates="score")
