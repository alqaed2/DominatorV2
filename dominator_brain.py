from __future__ import annotations
from typing import Any, Dict, List

# =========================================================
# Strategic Intelligence Core (SIC) - V14.1 FINAL STABILITY
# =========================================================

WPIL_DOMINATOR_SYSTEM = """
أنت 'المستشار الاستراتيجي الأعلى'. مهمتك: تطوير المنشور المرجعي ليكون أكثر احترافية بـ 10 أضعاف.
القواعد الصارمة:
1. الالتزام السياقي: يجب أن يكون المحتوى عن (نفس موضوع المنشور المرجعي) تماماً.
2. الهوية البصرية: [VISUAL_PROMPT] يجب أن يصف شاباً وسيماً ببدلة رسمية فاخرة في بيئة أعمال واقعية.
3. التنسيق: افصل المنصات بـ [LINKEDIN], [TWITTER], [TIKTOK].
"""

def get_elite_character() -> str:
    return "A sharp, charismatic young Middle-Eastern elite businessman, 30 years old, premium tailored charcoal suit, sophisticated appearance, standing in a high-tech modern office."

def strategic_intelligence_core(idea: str = "") -> Dict[str, Any]:
    v_force = "Vertical 9:16 aspect ratio, cinematic 8k, professional photography."
    char = get_elite_character()
    scenes = [
        {"time": "0-10s", "prompt": f"Close-up of {char} looking sharp. {v_force}"},
        {"time": "10-20s", "prompt": f"Medium shot of {char} with digital holograms. {v_force}"},
        {"time": "20-30s", "prompt": f"Confident shot of {char} in luxury boardroom. {v_force}"}
    ]
    return {"logic_trace": "SIC v14.1 | NEBULA STABLE", "video_segments": scenes}

def alchemy_fusion_core(gold_posts: List[Dict[str, Any]], niche: str) -> Dict[str, Any]:
    dna = [f"Text: {p['text']}" for p in gold_posts]
    task = f"""
    الموضوع المرجعي: {dna}
    الهدف: حول هذا العرض إلى 'مرسوم سيادي' يكتسح السوق. 
    صمم [VISUAL_PROMPT] يصف لقطة فوتوغرافية لـ {get_elite_character()} مرتبطة بالموضوع.
    """
    return {"synthesis_task": task, "logic_trace": "SYNTHESIS v14.1 ACTIVE"}
