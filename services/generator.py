from __future__ import annotations

from typing import Dict, List
import random


def generate_daily_brief(idea: str, language: str = "ar") -> Dict[str, str]:
    """
    Produces a compact daily brief for content execution.
    """
    if language == "ar":
        return {
            "hook": f"ابدأ بفكرة صادمة/فضولية عن: {idea}",
            "promise": "وعد واضح خلال أول 3 ثوانٍ",
            "structure": "Hook -> Context -> 3 نقاط -> CTA",
            "cta": "اكتب (جاهز) لأرسل لك نسخة سكربت كاملة",
        }
    return {
        "hook": f"Start with a curiosity hook about: {idea}",
        "promise": "Clear promise in the first 3 seconds",
        "structure": "Hook -> Context -> 3 points -> CTA",
        "cta": "Comment 'ready' and I’ll send a full script",
    }


def build_variants_for_idea(idea: str, count: int = 8, language: str = "ar") -> List[Dict[str, str]]:
    """
    Generates multiple angle variants for the same idea.
    """
    angles_ar = [
        "أسهل طريقة",
        "أكبر خطأ",
        "حقيقة غير متوقعة",
        "خطوات عملية",
        "قبل/بعد",
        "قصة قصيرة",
        "مقارنة سريعة",
        "اختبار بسيط",
    ]
    angles_en = [
        "Easiest way",
        "Biggest mistake",
        "Unexpected truth",
        "Actionable steps",
        "Before/After",
        "Short story",
        "Quick comparison",
        "Simple test",
    ]
    angles = angles_ar if language == "ar" else angles_en

    out = []
    for _ in range(max(1, count)):
        a = random.choice(angles)
        out.append(
            {
                "angle": a,
                "title": f"{a}: {idea}",
                "hook": f"{a} عن {idea}" if language == "ar" else f"{a} about {idea}",
            }
        )
    return out


class GeneratorService:
    """Backward-compatible wrapper for code that expects a service class."""

    @staticmethod
    def generate_daily_brief(idea: str, language: str = "ar"):
        return generate_daily_brief(idea=idea, language=language)

    @staticmethod
    def build_variants_for_idea(idea: str, count: int = 8, language: str = "ar"):
        return build_variants_for_idea(idea=idea, count=count, language=language)
