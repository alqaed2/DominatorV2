from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OnboardRequest(BaseModel):
    project_name: str = Field(..., min_length=1)
    niche: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    platforms: List[str] = Field(default_factory=lambda: ["tiktok", "reels", "shorts"])
    language: str = Field(default="ar")


class DailyBriefRequest(BaseModel):
    idea: str = Field(..., min_length=1)
    language: str = Field(default="ar")


class BuildPackRequest(BaseModel):
    title: str = Field(..., min_length=1)
    niche: str = Field(default="")
    audience: str = Field(default="")
    language: str = Field(default="ar")


class SubmitMetricsRequest(BaseModel):
    session_id: str = Field(..., min_length=8)
    platform: str = Field(..., min_length=1)
    content_id: str = Field(..., min_length=1)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    ts: Optional[str] = None


class ManualMetricsRequest(SubmitMetricsRequest):
    """Backward-compatible alias for older clients."""
    pass


class MetricsPoint(BaseModel):
    ts: str
    platform: str
    content_id: str
    metrics: Dict[str, Any]
