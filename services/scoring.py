from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math

from utils.logging import get_logger

log = get_logger("scoring")


@dataclass
class ScoreResult:
    score: float
    why: list[str]
    minimum_fix: str


def _clamp(x: float, a: float = 0.0, b: float = 100.0) -> float:
    return max(a, min(b, x))


def dominance_score_v1(hook_text: str, onscreen_text: str, blueprint: dict[str, Any]) -> ScoreResult:
    """
    TikTok dominance score v1:
    Deterministic heuristic scoring for MVP (calibrates later).
    """
    text = (hook_text or "").strip()
    ons = (onscreen_text or "").strip()

    why: list[str] = []

    # Retention intent (45)
    retention = 0.0
    if len(text) >= 12:
        retention += 12
        why.append("الهوك واضح بما يكفي لإثارة الانتباه خلال أول ثانية.")
    if "؟" in text or "?" in text:
        retention += 10
        why.append("وجود سؤال/فضول يزيد احتمالية المتابعة (Open Loop).")
    if any(k in text.lower() for k in ["خطأ", "سر", "سبب", "لا تفعل", "لن تصدق", "3", "5"]):
        retention += 10
        why.append("استخدام محفّز (خطأ/سر/قائمة) يرفع نية المشاهدة حتى النهاية.")
    if len(ons) >= 8:
        retention += 8
        why.append("نص الشاشة يدعم الفهم السريع ويقلل الهروب.")
    retention = min(45.0, retention)

    # Engagement triggers (30)
    engagement = 0.0
    cta = (blueprint.get("cta") or "").lower()
    if any(k in cta for k in ["اكتب", "علّق", "شارك", "احفظ", "follow", "comment"]):
        engagement += 10
        why.append("دعوة تفاعل واضحة (تعليق/حفظ/مشاركة) ترفع الإشارات.")
    value = (blueprint.get("value_promise") or "").lower()
    if any(k in value for k in ["خطوات", "قائمة", "قبل", "بعد", "مقارنة", "طريقة"]):
        engagement += 10
        why.append("قيمة قابلة للحفظ/المشاركة (قائمة/خطوات/قبل-بعد).")
    if any(k in text.lower() for k in ["رقم", "%", "نتيجة", "تجربة"]):
        engagement += 6
        why.append("وجود دليل/نتيجة مصغرة يزيد الثقة والتفاعل.")
    engagement = min(30.0, engagement)

    # Search & context (15)
    search = 0.0
    keywords = blueprint.get("keywords", [])
    if isinstance(keywords, list) and len(keywords) >= 2:
        search += 8
        why.append("كلمات مفتاحية متعددة تساعد في الظهور بالبحث (TikTok SEO).")
    hashtags = blueprint.get("hashtags", [])
    if isinstance(hashtags, list) and 2 <= len(hashtags) <= 4:
        search += 7
        why.append("هاشتاقات مركزة (2-4) أفضل من الحشو.")
    search = min(15.0, search)

    # Packaging (10)
    pack = 0.0
    length = int(blueprint.get("length_sec") or 0)
    if 15 <= length <= 45:
        pack += 6
        why.append("طول الفيديو ضمن نطاق مناسب للاستهلاك الكامل (قابل للاختبار).")
    if len(ons) > 0:
        pack += 4
        why.append("الـFrame الأول مدعوم بنص واضح (Packaging).")
    pack = min(10.0, pack)

    score = retention + engagement + search + pack

    # Minimum fix: pick the largest missing component
    gaps = {
        "retention": 45 - retention,
        "engagement": 30 - engagement,
        "search": 15 - search,
        "packaging": 10 - pack,
    }
    biggest_gap = max(gaps, key=gaps.get)

    fix_map = {
        "retention": "بدّل الهوك إلى سؤال/وعد محدد خلال 1 ثانية (Open Loop) مع نتيجة ملموسة.",
        "engagement": "أضف CTA واحدًا واضحًا: (اكتب كلمة X بالتعليقات) أو (احفظ الفيديو لقائمة الخطوات).",
        "search": "أضف 2-3 كلمات مفتاحية دقيقة في الوصف ونص الشاشة + 2-4 هاشتاقات مركزة.",
        "packaging": "ثبّت Frame أول واضح: عنوان كبير على الشاشة + جملة وعد قصيرة.",
    }

    minimum_fix = fix_map[biggest_gap]
    return ScoreResult(score=_clamp(score), why=why[:3], minimum_fix=minimum_fix)
