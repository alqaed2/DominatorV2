from __future__ import annotations

from typing import Dict, List


def build_blueprint(
    idea_title: str,
    angle: str,
    value_promise: str,
    video_seconds: int = 45,
    language: str = "ar",
) -> Dict:
    return {
        "idea_title": idea_title,
        "angle": angle,
        "value_promise": value_promise,
        "video_seconds": video_seconds,
        "beats": [
            {"t": 0, "label": "Hook"},
            {"t": 5, "label": "Context"},
            {"t": 12, "label": "Point 1"},
            {"t": 22, "label": "Point 2"},
            {"t": 32, "label": "Point 3"},
            {"t": 42, "label": "CTA"},
        ],
        "language": language,
    }


def render_ready_to_record_kit(blueprint: Dict, language: str = "ar") -> Dict:
    idea = blueprint.get("idea_title", "")
    angle = blueprint.get("angle", "")
    promise = blueprint.get("value_promise", "")
    if language == "ar":
        return {
            "script": f"هوك: {angle}\nالوعد: {promise}\nالمحتوى: 3 نقاط قوية عن {idea}\nCTA: تابعني للمزيد.",
            "caption": f"{angle} — {promise}",
            "shotlist": ["لقطة وجه قريبة", "نصوص على الشاشة", "B-roll داعم", "CTA نهائي"],
        }
    return {
        "script": f"Hook: {angle}\nPromise: {promise}\nBody: 3 strong points about {idea}\nCTA: Follow for more.",
        "caption": f"{angle} — {promise}",
        "shotlist": ["Close face shot", "On-screen text", "Supporting b-roll", "Final CTA"],
    }


def build_experiment_plan(
    title: str,
    niche: str = "",
    goal: str = "",
    platforms: List[str] | None = None,
    days: int = 7,
    language: str = "ar",
) -> Dict:
    platforms = platforms or ["tiktok", "reels", "shorts"]
    if language == "ar":
        return {
            "title": title,
            "goal": goal or "رفع التفاعل",
            "days": days,
            "platforms": platforms,
            "plan": [
                {"day": 1, "task": "انشر 2 فيديو بزوايا مختلفة"},
                {"day": 2, "task": "غيّر الهوك فقط وكرر"},
                {"day": 3, "task": "اختبر طول 30s vs 45s"},
                {"day": 4, "task": "اختبر CTA مختلف"},
                {"day": 5, "task": "ركز على أفضل زاوية"},
                {"day": 6, "task": "أعد إنتاج الأفضل بجودة أعلى"},
                {"day": 7, "task": "راجِع النتائج وقرّر التالي"},
            ],
        }
    return {
        "title": title,
        "goal": goal or "Increase engagement",
        "days": days,
        "platforms": platforms,
        "plan": [
            {"day": 1, "task": "Post 2 videos with different angles"},
            {"day": 2, "task": "Change only the hook and repeat"},
            {"day": 3, "task": "Test 30s vs 45s length"},
            {"day": 4, "task": "Test a different CTA"},
            {"day": 5, "task": "Double down on best angle"},
            {"day": 6, "task": "Reproduce best with higher quality"},
            {"day": 7, "task": "Review results and decide next"},
        ],
    }


def build_prompt_pack(
    title: str,
    style: str = "cinematic",
    outputs: List[str] | None = None,
    language: str = "ar",
) -> Dict:
    outputs = outputs or ["thumbnail", "b-roll", "caption"]
    if language == "ar":
        return {
            "title": title,
            "style": style,
            "outputs": outputs,
            "prompts": {
                "thumbnail": f"صمّم ثمنيل {style} بعنوان: {title}",
                "b-roll": f"اقترح لقطات B-roll {style} تدعم فيديو بعنوان: {title}",
                "caption": f"اكتب كابشن عربي قوي لفيديو بعنوان: {title}",
            },
        }
    return {
        "title": title,
        "style": style,
        "outputs": outputs,
        "prompts": {
            "thumbnail": f"Design a {style} thumbnail titled: {title}",
            "b-roll": f"Suggest {style} B-roll shots for a video titled: {title}",
            "caption": f"Write a strong caption for a video titled: {title}",
        },
    }


class ArtifactsService:
    """Backward-compatible wrapper for code that expects a service class."""

    @staticmethod
    def build_blueprint(
        idea_title: str,
        angle: str,
        value_promise: str,
        video_seconds: int = 45,
        language: str = "ar",
    ):
        return build_blueprint(
            idea_title=idea_title,
            angle=angle,
            value_promise=value_promise,
            video_seconds=video_seconds,
            language=language,
        )

    @staticmethod
    def render_ready_to_record_kit(blueprint: dict, language: str = "ar"):
        return render_ready_to_record_kit(blueprint=blueprint, language=language)

    @staticmethod
    def build_experiment_plan(
        title: str,
        niche: str = "",
        goal: str = "",
        platforms: list[str] | None = None,
        days: int = 7,
        language: str = "ar",
    ):
        return build_experiment_plan(
            title=title,
            niche=niche,
            goal=goal,
            platforms=platforms or ["tiktok", "reels", "shorts"],
            days=days,
            language=language,
        )

    @staticmethod
    def build_prompt_pack(
        title: str,
        style: str = "cinematic",
        outputs: list[str] | None = None,
        language: str = "ar",
    ):
        return build_prompt_pack(
            title=title,
            style=style,
            outputs=outputs or ["thumbnail", "b-roll", "caption"],
            language=language,
        )
