from pydantic import BaseModel, Field
from typing import Any, Literal


class OnboardRequest(BaseModel):
    display_name: str = Field(default="New Creator")
    goal: Literal["followers", "sales", "authority"] = "followers"
    primary_niche: str
    sub_niches: list[str] = []
    language: Literal["ar", "en"] = "ar"
    tone: Literal["educational", "story", "funny", "mixed"] = "educational"
    constraints: dict[str, Any] = {}
    tiktok_profile_url: str | None = None

    # Optional: examples for stronger DNA
    top_video_urls: list[str] = []
    weak_video_urls: list[str] = []
    past_scripts: list[str] = []


class OnboardResponse(BaseModel):
    creator_id: str
    mode_default: Literal["manual"] = "manual"
    message: str


class DailyBriefRequest(BaseModel):
    creator_id: str
    competitor_urls: list[str] = []
    extra_context: str | None = None


class HookVariant(BaseModel):
    key: Literal["A", "B", "C"]
    hook_text: str
    onscreen_text: str
    score: float
    why: list[str]
    minimum_fix: str


class IdeaBrief(BaseModel):
    title: str
    angle: str
    value_promise: str
    variants: list[HookVariant]


class DailyBriefResponse(BaseModel):
    creator_id: str
    ideas: list[IdeaBrief]


class BuildPackRequest(BaseModel):
    creator_id: str
    idea_title: str
    angle: str
    value_promise: str
    preferred_length_sec: int = 28
    mode: Literal["kit", "prompt_pack", "both"] = "kit"


class Artifact(BaseModel):
    type: Literal["ready_to_record_kit", "prompt_pack", "experiment_plan"]
    payload: dict


class BuildPackResponse(BaseModel):
    experiment_id: str
    artifacts: list[Artifact]
    predicted: dict


class MetricsPoint(BaseModel):
    t_label: Literal["T+60m", "T+24h", "T+48h"]
    views: int
    likes: int
    comments: int
    shares: int
    followers_gained: int | None = None
    profile_visits: int | None = None


class SubmitMetricsRequest(BaseModel):
    creator_id: str
    experiment_id: str
    variant_key: Literal["A", "B", "C"]
    point: MetricsPoint


class SubmitMetricsResponse(BaseModel):
    experiment_id: str
    status: str
    winner: str | None
    lift: dict


class ReportResponse(BaseModel):
    experiment_id: str
    creator_id: str
    status: str
    winner: str | None
    predicted_scores: dict
    lift: dict
    proof_artifact: dict
