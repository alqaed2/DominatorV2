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

    tiktok_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    baseline_views: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_share_rate: Mapped[float] = mapped_column(Float, default=0.0)

    genome = relationship("Genome", back_populates="creator", uselist=False, cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="creator", cascade="all, delete-orphan")


class Genome(Base):
    __tablename__ = "genomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    creator_id: Mapped[str] = mapped_column(String(36), ForeignKey("creators.id"), unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # JSON blob string with creator DNA (hook archetypes, pacing prefs, vocab, etc.)
    creator_dna_json: Mapped[str] = mapped_column(Text, default="{}")

    # Learned weights/calibration
    calibration_json: Mapped[str] = mapped_column(Text, default="{}")

    creator = relationship("Creator", back_populates="genome")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    creator_id: Mapped[str] = mapped_column(String(36), ForeignKey("creators.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft|running|completed

    idea_title: Mapped[str] = mapped_column(String(200))
    blueprint_json: Mapped[str] = mapped_column(Text, default="{}")  # content blueprint

    # Variants (A/B/C)
    variant_a_json: Mapped[str] = mapped_column(Text, default="{}")
    variant_b_json: Mapped[str] = mapped_column(Text, default="{}")
    variant_c_json: Mapped[str] = mapped_column(Text, default="{}")

    predicted_score_a: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_score_b: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_score_c: Mapped[float] = mapped_column(Float, default=0.0)

    winner: Mapped[str | None] = mapped_column(String(1), nullable=True)  # A|B|C

    # Metrics snapshots stored as JSON string
    metrics_json: Mapped[str] = mapped_column(Text, default="[]")

    # Lift summary
    lift_views: Mapped[float] = mapped_column(Float, default=0.0)
    lift_share_rate: Mapped[float] = mapped_column(Float, default=0.0)
    lift_engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)

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
