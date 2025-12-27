# wpil_runtime.py
# WPIL Runtime Interface (No-evaluation, no-rejection)
from typing import Dict, Any


def invoke_wpil(content_signal: Dict[str, Any]) -> Dict[str, Any]:
    platform = (content_signal.get("platform") or "linkedin").lower().strip()
    niche = (content_signal.get("niche") or "general").strip()
    winning_post = (content_signal.get("winning_post") or "").strip()

    # Default constraints (بنيوية فقط)
    constraints = {
        "hook": {"type": "bold_claim", "max_words": 12},
        "structure": {"line_density": "one_idea_per_line", "avg_sentence_words": 14},
        "cta": {"type": "question", "position": "end"}
    }

    mode = "direct"
    notes = "defaults"

    # لو المستخدم لصق Winning Post: نفعّل Remix Mode ونزيد الانضباط البنيوي
    if len(winning_post) > 20:
        mode = "remix"
        notes = f"remix enabled for niche={niche}"
        if platform == "twitter":
            constraints["thread"] = {"tweets": "5-7", "max_lines_per_tweet": 4}
        if platform == "linkedin":
            constraints["length_hint"] = {"words": "120-220"}
        if platform == "tiktok":
            constraints["video"] = {"seconds": "45-70", "shots": "5-8"}

    return {
        "mode": mode,
        "constraints": constraints,
        "notes": notes
    }
