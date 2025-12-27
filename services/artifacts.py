from __future__ import annotations
from typing import Any
import uuid


def build_ready_to_record_kit(
    idea_title: str,
    blueprint: dict[str, Any] ,
    variant: dict[str, Any],
) -> dict[str, Any]:
    """
    Returns a structured bundle that a creator can record manually.
    """
    length = int(blueprint.get("length_sec", 28))
    hook = variant["hook_text"]
    onscreen_hook = variant["onscreen_text"]

    # Simple timeline template
    timeline = {
        "video_seconds": length,
        "sections": [
            {"t_start": 0, "t_end": 2, "type": "hook", "text": hook, "onscreen": onscreen_hook},
            {"t_start": 2, "t_end": 8, "type": "problem", "text": blueprint["problem"], "onscreen": blueprint["problem_onscreen"]},
            {"t_start": 8, "t_end": max(20, length - 6), "type": "solution", "text": blueprint["solution"], "onscreen": blueprint["solution_onscreen"]},
            {"t_start": max(20, length - 6), "t_end": length, "type": "cta", "text": blueprint["cta"], "onscreen": blueprint["cta_onscreen"]},
        ],
    }

    kit = {
        "id": str(uuid.uuid4()),
        "title": idea_title,
        "script_teleprompter": blueprint["script"].replace("{{HOOK}}", hook),
        "timeline": timeline,
        "onscreen_text_srt": blueprint["onscreen_srt"].replace("{{HOOK}}", onscreen_hook),
        "shot_list": blueprint["shot_list"],
        "edit_cues": blueprint["edit_cues"],
        "caption": blueprint["caption"],
        "keywords": blueprint["keywords"],
        "hashtags": blueprint["hashtags"],
        "hooks": {
            "A": blueprint["hooks"]["A"],
            "B": blueprint["hooks"]["B"],
            "C": blueprint["hooks"]["C"],
        }
    }
    return kit


def build_prompt_pack(idea_title: str, blueprint: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": idea_title,
        "prompts": {
            "script": blueprint["prompt_script"],
            "hooks": blueprint["prompt_hooks"],
            "editing": blueprint["prompt_editing"],
            "visual": blueprint["prompt_visual"],
            "next_series": blueprint["prompt_next_series"],
        }
    }


def build_experiment_plan(blueprint: dict[str, Any]) -> dict[str, Any]:
    return {
        "what_to_test": [
            "Hook A/B/C (أول 1-2 ثانية)",
            "Length (قصير/متوسط عند الحاجة)",
            "Caption keywords + On-screen text",
            "Audio (Trending vs Original إذا كان مناسبًا)"
        ],
        "measurement_points": ["T+60m", "T+24h", "T+48h"],
        "win_function": {
            "phase_1": ["views_velocity (60-180m)", "shares_per_1k_views"],
            "phase_2": ["comments_per_1k_views", "engagement_rate", "follow_rate_if_available"],
        },
        "next_best_action": "إذا فاز Variant ما: اصنع Part 2 بنفس الزاوية مع تطعيم معلومة جديدة."
    }
