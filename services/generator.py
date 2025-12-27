from typing import Any, Dict, List

from services.scoring import score_hook  # إذا لم يكن عندك services/scoring.py، أخبرني وسأدمج الدالة هنا فورًا


def _why_common() -> List[str]:
    return [
        "الهوك واضح بما يكفي لإثارة الانتباه خلال أول ثانية.",
        "وجود فضول/وعد واضح يزيد احتمالية المتابعة (Open Loop).",
        "استخدام محفّز (خطأ/قائمة/زمن) يرفع نية المشاهدة حتى النهاية.",
    ]


def generate_daily_brief(
    primary_niche: str,
    language: str = "ar",
    tone: str = "educational",
    competitor_urls: List[str] | None = None,
    extra_context: str = "",
) -> List[Dict[str, Any]]:
    """
    Produces 3 ideas + variants A/B/C per idea.
    """
    niche = (primary_niche or "مجالك").strip()

    ideas = [
        {
            "angle": "تفكيك خطأ + بديل عملي",
            "title": f"خطأ شائع يمنعك من النجاح في {niche}",
            "value_promise": "خطوة واحدة تصحح المسار خلال يوم واحد.",
        },
        {
            "angle": "قائمة خطوات قابلة للحفظ",
            "title": f"3 خطوات سريعة لتحسين نتائجك في {niche}",
            "value_promise": "خطة بسيطة: نفّذ، قِس، عدّل.",
        },
        {
            "angle": "سبب جذري + علاج مباشر",
            "title": f"السبب الحقيقي لعدم تقدمك في {niche} (والحل)",
            "value_promise": "تغيير صغير يرفع نتائجك بشكل ملحوظ.",
        },
    ]

    out = []
    for it in ideas:
        variants = build_variants_for_idea(title=it["title"], angle=it["angle"], niche=niche)
        it2 = dict(it)
        it2["variants"] = variants
        out.append(it2)

    return out


def build_variants_for_idea(title: str, angle: str, niche: str) -> List[Dict[str, Any]]:
    """
    IMPORTANT CHANGE:
    Variant B adapts to the idea title.
    - If the idea is "3 خطوات..." => B becomes "3 خطوات..." (not "3 أخطاء...").
    """
    title = (title or "").strip()
    niche = (niche or "مجالك").strip()

    minimum_fix = "أضف CTA واحدًا واضحًا: (اكتب كلمة X بالتعليقات) أو (احفظ الفيديو لقائمة الخطوات)."

    # A: pain-based
    hook_a = f"إذا كنت في {niche} وتفعل هذا… فأنت تخسر بدون أن تدري."
    on_a = f"توقف عن هذا في {niche}!"

    # B: title-adaptive list/curiosity
    if "3 خطوات" in title:
        hook_b = f"3 خطوات ترفع نتائجك في {niche}… الخطوة 2 تغيّر اللعبة."
        on_b = "3 خطوات سريعة"
    else:
        hook_b = f"3 أخطاء تمنعك من التقدم في {niche}… رقم 2 صادم."
        on_b = "3 أخطاء قاتلة"

    # C: time-bound promise
    hook_c = f"في أقل من 30 ثانية… طريقة عملية لتحسن نتيجتك في {niche}."
    on_c = "طريقة خلال 30 ثانية"

    variants = [
        {
            "key": "A",
            "hook_text": hook_a,
            "onscreen_text": on_a,
            "minimum_fix": minimum_fix,
            "why": _why_common(),
            "score": float(score_hook(hook_a, on_a)),
        },
        {
            "key": "B",
            "hook_text": hook_b,
            "onscreen_text": on_b,
            "minimum_fix": minimum_fix,
            "why": _why_common(),
            "score": float(score_hook(hook_b, on_b)),
        },
        {
            "key": "C",
            "hook_text": hook_c,
            "onscreen_text": on_c,
            "minimum_fix": minimum_fix,
            "why": _why_common(),
            "score": float(score_hook(hook_c, on_c)),
        },
    ]

    return variants
