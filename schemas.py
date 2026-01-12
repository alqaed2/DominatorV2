from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any


class BuildPackRequest(BaseModel):
    mode: str = Field(default="niche", description="niche|url")
    niche: str | None = None
    url: str | None = None

    platforms: list[str] = Field(default_factory=lambda: ["linkedin", "x", "tiktok"])
    language: str = "ar"
    tone: str = "authority"
    include_visual: bool = True

    # optional: force sync processing even if async enabled
    sync: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    pack_id: str | None = None
    error: str | None = None


class PackResponse(BaseModel):
    pack_id: str
    job_id: str | None = None

    mode: str
    input_value: str
    language: str
    platforms: list[str]
    tone: str

    genes: dict[str, Any] = {}
    assets: dict[str, Any] = {}
    visual: dict[str, Any] = {}
    dominance: dict[str, Any] = {}
    sources: dict[str, Any] = {}
