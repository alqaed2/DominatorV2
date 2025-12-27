from __future__ import annotations
from typing import Any
import random
import textwrap

from config import settings
from utils.logging import get_logger
from services.scoring import dominance_score_v1

log = get_logger("generator")


def _basic_keywords(niche: str) -> list[str]:
    base = [niche.strip()]
    if len(niche.split()) >= 2:
        base.append(niche.split()[0])
    return list(dict.fromkeys([k for k in base if k]))


def _basic_hashtags(niche: str) -> list[str]:
    # keep 2-4 as recommended
    tag = niche.replace(" ", "")
    return [f"#{tag}", "#تعلم", "#نصائح"][:3]


def build_blueprint(
    creator: dict[str, Any],
    idea_title: str,
    angle: str,
    value_promise: str,
    preferred_length_sec: int = 28,
) -> dict[str, Any]:
    """
    Deterministic blueprint builder for MVP.
    Later we can plug LLM here with structured JSON output.
    """
    niche = creator["primary_niche"]
    tone = creator["tone"]
    lang = creator["language"]

    keywords = _basic_keywords(niche)
    hashtags = _basic_hashtags(niche)

    # Script skeleton (Arabic-first)
    hook_placeholder = "{{HOOK}}"
    problem = f"معظم الناس في {niche} يقعوا في خطأ واحد…"
    solution = f"الحل في 3 خطوات: (1) حدد الهدف بدقة، (2) نفّذ خطوة واحدة اليوم، (3) راقب النتيجة وعدّل."
    cta = "اكتب كلمة (جاهز) بالتعليقات وسأرسل لك الخطوات بشكل أوضح."

    script = textwrap.dedent(f"""
    {hook_placeholder}
    {problem}
    {solution}
    {cta}
    """).strip()

    onscreen_srt = textwrap.dedent(f"""
    1
    00:00:00,000 --> 00:00:02,000
    {{HOOK}}

    2
    00:00:02,000 --> 00:00:08,000
    {problem}

    3
    00:00:08,000 --> 00:00:22,000
    {solution}

    4
    00:00:22,000 --> 00:00:28,000
    {cta}
    """).strip()

    edit_cues = [
        "تغيير لقطة/زووم بسيط كل 1.5–2 ثانية.",
        "أظهر الكلمات المفتاحية على الشاشة.",
        "اجعل الـHook بصوت قوي + نص كبير."
    ]
    shot_list = [
        "لقطة قريبة للوجه/المتحدث مع إضاءة جيدة.",
        "B-roll بسيط أثناء ذكر الخطوات.",
        "لقطة ختام مع CTA على الشاشة."
    ]

    hooks = {
        "A": {"hook_text": f"إذا كنت في {niche} وتفعل هذا… فأنت تخسر بدون أن تدري.", "onscreen_text": f"توقف عن هذا في {niche}!"},
        "B": {"hook_text": f"3 أخطاء تمنعك من التقدم في {niche}… رقم 2 صادم.", "onscreen_text": "3 أخطاء قاتلة"},
        "C": {"hook_text": f"في أقل من 30 ثانية… سأعطيك طريقة عملية لتحسن نتيجتك في {niche}.", "onscreen_text": "طريقة خلال 30 ثانية"},
    }

    blueprint = {
        "title": idea_title,
        "angle": angle,
        "value_promise": value_promise,
        "length_sec": int(preferred_length_sec),

        "problem": problem,
        "problem_onscreen": "الخطأ الشائع",
        "solution": solution,
        "solution_onscreen": "الحل (3 خطوات)",
        "cta": cta,
        "cta_onscreen": "اكتب (جاهز) 👇",

        "script": script,
        "onscreen_srt": onscreen_srt,
        "edit_cues": edit_cues,
        "shot_list": shot_list,
        "caption": f"{value_promise}\n# {niche}",
        "keywords": keywords,
        "hashtags": hashtags,
        "hooks": hooks,

        # Prompt pack templates (for external generation)
        "prompt_script": f"اكتب سكربت TikTok ({preferred_length_sec} ثانية) عن: {idea_title} بزاوية: {angle} وبقيمة: {value_promise}. ابدأ بهوك قوي خلال 1 ثانية.",
        "prompt_hooks": f"ولّد 3 Hooks مختلفة (A/B/C) عن {idea_title}، كل Hook <= 14 كلمة، مع نص شاشة قصير.",
        "prompt_editing": "اقترح إرشادات مونتاج سريع: تقطيع، تكبير، نص على الشاشة كل 1-2 ثانية، مع إيقاع عالي.",
        "prompt_visual": "اقترح شكل بصري للـFrame الأول + نص كبير واضح + ألوان متناسقة.",
        "prompt_next_series": f"اقترح 5 أفكار (Part 2/3/4) مبنية على نفس زاوية {angle} لتعزيز سلسلة محتوى."
    }
    return blueprint


def generate_daily_ideas(creator: dict[str, Any], competitor_urls: list[str] | None = None) -> list[dict[str, Any]]:
    """
    MVP: generate 3 idea candidates deterministically.
    """
    niche = creator["primary_niche"]
    goal = creator["goal"]

    candidates = [
        {
            "title": f"خطأ شائع يمنعك من النجاح في {niche}",
            "angle": "تفكيك خطأ + بديل عملي",
            "value_promise": "خطوة واحدة تصحح المسار خلال يوم واحد."
        },
        {
            "title": f"3 خطوات سريعة لتحسين نتائجك في {niche}",
            "angle": "قائمة خطوات قابلة للحفظ",
            "value_promise": "خطة بسيطة: نفّذ، قِس، عدّل."
        },
        {
            "title": f"السبب الحقيقي لعدم تقدمك في {niche} (والحل)",
            "angle": "سبب جذري + علاج مباشر",
            "value_promise": "تغيير صغير يرفع نتائجك بشكل ملحوظ."
        },
    ]
    return candidates


def score_variants(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Returns scored variants with why+minimum_fix.
    """
    out = {}
    for key in ["A", "B", "C"]:
        v = blueprint["hooks"][key]
        res = dominance_score_v1(v["hook_text"], v["onscreen_text"], blueprint)
        out[key] = {
            "hook_text": v["hook_text"],
            "onscreen_text": v["onscreen_text"],
            "score": float(res.score),
            "why": res.why,
            "minimum_fix": res.minimum_fix,
        }
    return out
