from typing import Any, Dict, List

# Safe tokens (no conflict with f-strings, no {HOOK} leakage)
HOOK_TEXT_TOKEN = "%%HOOK_TEXT%%"
HOOK_ONSCREEN_TOKEN = "%%HOOK_ONSCREEN%%"


def build_blueprint(idea_title: str, angle: str, value_promise: str, video_seconds: int = 28) -> Dict[str, Any]:
    """
    Builds a deterministic blueprint using safe tokens.
    This eliminates the {HOOK} placeholder bug permanently.
    """
    idea_title = (idea_title or "").strip()
    angle = (angle or "").strip()
    value_promise = (value_promise or "").strip()
    video_seconds = int(video_seconds or 28)

    caption = f"{idea_title}: {value_promise}\n# {idea_title.split(' ')[0] if idea_title else 'نصائح'}"

    script = (
        f"{HOOK_TEXT_TOKEN}\n"
        "معظم الناس يقعوا في خطأ واحد…\n"
        "الحل في 3 خطوات: (1) هدف واضح، (2) خطوة واحدة اليوم، (3) قياس وتعديل.\n"
        "اكتب كلمة (خطة) بالتعليقات وسأرسل لك نسخة مختصرة."
    )

    onscreen_srt = (
        "1\n00:00:00,000 --> 00:00:02,000\n"
        f"{HOOK_ONSCREEN_TOKEN}\n\n"
        "2\n00:00:02,000 --> 00:00:08,000\n"
        "معظم الناس يقعوا في خطأ واحد…\n\n"
        "3\n00:00:08,000 --> 00:00:22,000\n"
        "الحل في 3 خطوات: (1) هدف واضح، (2) خطوة واحدة اليوم، (3) قياس وتعديل.\n\n"
        "4\n00:00:22,000 --> 00:00:28,000\n"
        "اكتب (خطة) بالتعليقات وسأرسل لك نسخة مختصرة."
    )

    timeline = {
        "video_seconds": video_seconds,
        "sections": [
            {
                "type": "hook",
                "t_start": 0,
                "t_end": 2,
                "text": HOOK_TEXT_TOKEN,
                "onscreen": HOOK_ONSCREEN_TOKEN,
            },
            {
                "type": "problem",
                "t_start": 2,
                "t_end": 8,
                "text": "معظم الناس يقعوا في خطأ واحد…",
                "onscreen": "الخطأ الشائع",
            },
            {
                "type": "solution",
                "t_start": 8,
                "t_end": 22,
                "text": "الحل في 3 خطوات: (1) هدف واضح، (2) خطوة واحدة اليوم، (3) قياس وتعديل.",
                "onscreen": "الحل (3 خطوات)",
            },
            {
                "type": "cta",
                "t_start": 22,
                "t_end": 28,
                "text": "اكتب كلمة (خطة) بالتعليقات وسأرسل لك نسخة مختصرة.",
                "onscreen": "اكتب (خطة) 👇",
            },
        ],
    }

    return {
        "title": idea_title,
        "angle": angle,
        "value_promise": value_promise,
        "caption": caption,
        "script": script,
        "onscreen_srt": onscreen_srt,
        "timeline": timeline,
    }


def render_ready_to_record_kit(
    blueprint: Dict[str, Any],
    selected_hook_text: str,
    selected_onscreen_text: str,
    hooks_map: Dict[str, Dict[str, str]],
    keywords: List[str],
) -> Dict[str, Any]:
    """
    Renders a ready-to-record kit with tokens replaced deterministically.
    """
    script_final = (blueprint.get("script") or "").replace(HOOK_TEXT_TOKEN, selected_hook_text)
    srt_final = (blueprint.get("onscreen_srt") or "").replace(HOOK_ONSCREEN_TOKEN, selected_onscreen_text)

    # copy timeline with replacements
    timeline = blueprint.get("timeline") or {"video_seconds": 28, "sections": []}
    new_sections = []
    for s in timeline.get("sections", []):
        ss = dict(s)
        if ss.get("text") == HOOK_TEXT_TOKEN:
            ss["text"] = selected_hook_text
        if ss.get("onscreen") == HOOK_ONSCREEN_TOKEN:
            ss["onscreen"] = selected_onscreen_text
        new_sections.append(ss)

    kit = {
        "id": str(__import__("uuid").uuid4()),
        "title": blueprint.get("title", ""),
        "caption": blueprint.get("caption", ""),
        "hashtags": ["#التسويق_الرقمي", "#تعلم", "#نصائح"],
        "keywords": keywords or [],
        "hooks": hooks_map or {},
        "script_teleprompter": script_final,
        "onscreen_text_srt": srt_final,
        "timeline": {"video_seconds": timeline.get("video_seconds", 28), "sections": new_sections},
        "shot_list": [
            "لقطة قريبة للوجه/المتحدث مع إضاءة جيدة.",
            "B-roll بسيط أثناء ذكر الخطوات.",
            "لقطة ختام مع CTA على الشاشة.",
        ],
        "edit_cues": [
            "تغيير لقطة/زووم بسيط كل 1.5–2 ثانية.",
            "أظهر الكلمات المفتاحية على الشاشة.",
            "اجعل الـHook بصوت قوي + نص كبير.",
        ],
    }
    return kit


def build_experiment_plan() -> Dict[str, Any]:
    return {
        "measurement_points": ["T+60m", "T+24h", "T+48h"],
        "what_to_test": [
            "Hook A/B/C (أول 1-2 ثانية)",
            "Length (قصير/متوسط عند الحاجة)",
            "Caption keywords + On-screen text",
            "Audio (Trending vs Original إذا كان مناسبًا)",
        ],
        "win_function": {
            "phase_1": ["views_velocity (60-180m)", "shares_per_1k_views"],
            "phase_2": ["comments_per_1k_views", "engagement_rate", "follow_rate_if_available"],
        },
        "next_best_action": "إذا فاز Variant ما: اصنع Part 2 بنفس الزاوية مع تطعيم معلومة جديدة.",
    }


def build_prompt_pack(idea_title: str, angle: str, value_promise: str) -> Dict[str, Any]:
    idea_title = (idea_title or "").strip()
    angle = (angle or "").strip()
    value_promise = (value_promise or "").strip()

    return {
        "title": idea_title,
        "prompts": {
            "hooks": f"ولّد 3 Hooks مختلفة (A/B/C) عن {idea_title}، كل Hook <= 14 كلمة، مع نص شاشة قصير.",
            "script": f"اكتب سكربت TikTok (28 ثانية) عن: {idea_title} بزاوية: {angle} وبقيمة: {value_promise}. ابدأ بهوك قوي خلال 1 ثانية.",
            "editing": "اقترح إرشادات مونتاج سريع: تقطيع، تكبير، نص على الشاشة كل 1-2 ثانية، مع إيقاع عالي.",
            "visual": "اقترح شكل بصري للـFrame الأول + نص كبير واضح + ألوان متناسقة.",
            "next_series": f"اقترح 5 أفكار (Part 2/3/4) مبنية على نفس زاوية {angle} لتعزيز سلسلة محتوى.",
        },
    }
