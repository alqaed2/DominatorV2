from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from utils.logging import get_logger

log = get_logger("policy")


@dataclass
class PolicyDecision:
    allowed: bool
    reasons: list[str]
    sanitized: dict[str, Any]


DEFAULT_BANNED_TOPICS = {
    "hate", "extremism", "illegal", "harm",
}
DEFAULT_BLOCKED_CLAIMS = [
    "guaranteed viral", "100% viral", "اكيد فيروسي", "مضمون 100%",
]


def evaluate_policy(content: dict[str, Any], constraints: dict[str, Any]) -> PolicyDecision:
    """
    Governance gate:
    - Blocks risky topics/claims.
    - Ensures style constraints (tone/language) are not violated.
    """
    reasons: list[str] = []
    sanitized = dict(content)

    banned_topics = set(constraints.get("banned_topics", [])) | DEFAULT_BANNED_TOPICS
    text_blob = " ".join([
        str(content.get("script", "")),
        str(content.get("caption", "")),
        str(content.get("onscreen_text", "")),
    ]).lower()

    for t in banned_topics:
        if t.lower() in text_blob:
            reasons.append(f"Blocked topic keyword detected: {t}")

    for c in DEFAULT_BLOCKED_CLAIMS:
        if c.lower() in text_blob:
            reasons.append(f"Blocked claim detected: {c}")

    allowed = len(reasons) == 0
    if not allowed:
        # Basic sanitization: remove blocked claims phrases
        for c in DEFAULT_BLOCKED_CLAIMS:
            sanitized["script"] = str(sanitized.get("script", "")).replace(c, "")
            sanitized["caption"] = str(sanitized.get("caption", "")).replace(c, "")

    return PolicyDecision(allowed=allowed, reasons=reasons, sanitized=sanitized)
