from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    audience: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platforms: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    onboarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    metric_events: Mapped[List["MetricEvent"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MetricEvent(Base):
    __tablename__ = "metric_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    content_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # JSON works on Postgres + SQLite
    metrics_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # stored as ISO string for simplicity/compatibility
    ts: Mapped[str] = mapped_column(String(64), nullable=False)

    session: Mapped["SessionModel"] = relationship(back_populates="metric_events")
