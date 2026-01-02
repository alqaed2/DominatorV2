# services/generator.py
from __future__ import annotations

from typing import Any, Dict, List

from services.scoring import score_hook


def build_variants_for_idea(idea: Dict[str, Any], language: str = "ar", count: int = 3) -> List[Dict[str, Any]]:
    """
    Build A/B/C variants for a given idea.
    """
    base = {
        "title": idea.get("title", ""),
        "hook": idea.get("hook", ""),
        "language": language,
    }

    variants = []
    for idx, key in enumerate(["A", "B", "C"][:count]):
        hook = f"{base['hook']} ({key})" if base["hook"] else f"Variant {key}"
        variants.append(
            {
                "key": key,
                "title": base["title"],
                "hook": hook,
                "score": score_hook(hook),
            }
        )
    return variants


def generate_daily_brief(
    primary_niche: str,
    language: str = "ar",
    tone: str = "balanced",
    competitor_urls: List[str] | None = None,
    extra_context: str | None = None,
) -> Dict[str, Any]:
    """
    Generates a lightweight daily brief payload.
    """
    competitor_urls = competitor_urls or []
    extra_context = extra_context or ""

    # NOTE: يمكنك توسيع المنطق لاحقًا، هذا مجرد “قالب آمن” يمنع انهيار السيرفر.
    ideas = [
        {
            "title": f"Idea in {primary_niche}",
            "hook": f"Strong hook for {primary_niche}",
            "score": score_hook(f"Strong hook for {primary_niche}"),
        }
    ]

    return {
        "niche": primary_niche,
        "language": language,
        "tone": tone,
        "competitors": competitor_urls,
        "context": extra_context,
        "ideas": ideas,
    }


class GeneratorService:
    """
    Backward compatible service wrapper.

    - Old code may import: from services.generator import GeneratorService
    - New code may import: from services import generator as generator_svc

    This class guarantees both work without breaking deploy.
    """

    def build_variants_for_idea(self, idea: Dict[str, Any], language: str = "ar", count: int = 3) -> List[Dict[str, Any]]:
        return build_variants_for_idea(idea, language=language, count=count)

    def generate_daily_brief(
        self,
        primary_niche: str,
        language: str = "ar",
        tone: str = "balanced",
        competitor_urls: List[str] | None = None,
        extra_context: str | None = None,
    ) -> Dict[str, Any]:
        return generate_daily_brief(
            primary_niche=primary_niche,
            language=language,
            tone=tone,
            competitor_urls=competitor_urls,
            extra_context=extra_context,
        )
