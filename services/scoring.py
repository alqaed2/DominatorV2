from __future__ import annotations

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def score_hook(hook_text: str, onscreen_text: str) -> float:
    """
    Heuristic TikTok hook scoring (MVP):
    - prefers short, specific hooks
    - boosts curiosity triggers (رقم 2، صادم، خلال...)
    - boosts clarity and numeric cues
    Returns: 50..95
    """
    t = (hook_text or "").strip()
    o = (onscreen_text or "").strip()

    score = 68.0

    # Length (shorter tends to win)
    if len(t) <= 50:
        score += 6.0
    if len(t) <= 35:
        score += 4.0
    if len(t) <= 22:
        score += 2.0

    # Curiosity / pattern triggers
    triggers = [
        "رقم", "صادم", "يفاجئك", "تغيّر اللعبة", "بدون", "خلال", "سر",
        "خطأ", "أخطاء", "خطوات", "طريقة", "قبل ما", "لا تفعل", "توقف"
    ]
    for w in triggers:
        if w in t:
            score += 1.2

    # On-screen text should be punchy
    if 0 < len(o) <= 20:
        score += 2.0
    if any(ch.isdigit() for ch in (t + o)):
        score += 2.0

    # Penalize very vague hooks
    vague = ["شيء", "موضوع", "كلام", "مرة", "أحيانًا"]
    for w in vague:
        if w in t:
            score -= 0.8

    return float(clamp(score, 50.0, 95.0))
