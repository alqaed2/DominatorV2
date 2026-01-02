import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    display_name: Mapped[str] = mapped_column(String(120), default="New Creator")
    goal: Mapped[str] = mapped_column(String(40), default="followers")  # followers|sales|authority
    primary_niche: Mapped[str] = mapped_column(String(120))
    sub_niches: Mapped[str] = mapped_column(Text, default="[]")  # JSON list string

    language: Mapped[str] = mapped_column(String(20), default="ar")
    tone: Mapped[str] = mapped_column(String(40), default="educational")  # educational|story|funny|mixed
    constraints_json: Mapped[str] = mapped_column(Text, default="{}")

    experiments = relationship("Experiment", back_populates="creator")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator_id: Mapped[str] = mapped_column(String(36), ForeignKey("creators.id"), index=True)
    idea_title: Mapped[str] = mapped_column(String(240), default="")
    angle: Mapped[str] = mapped_column(String(240), default="")
    niche: Mapped[str] = mapped_column(String(120), default="general")

    mode: Mapped[str] = mapped_column(String(20), default="kit")  # kit|score|both
    variants_json: Mapped[str] = mapped_column(Text, default="{}")
    predicted_scores_json: Mapped[str] = mapped_column(Text, default="{}")

    # manual metrics snapshots (T+60m / 24h / 48h), JSON list
    metrics_json: Mapped[str] = mapped_column(Text, default="[]")

    is_winner_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    winner_key: Mapped[str] = mapped_column(String(4), default="")

    creator = relationship("Creator", back_populates="experiments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(10), default="INFO")  # INFO|WARN|ERROR

    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
