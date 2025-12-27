# wpil_selector.py
# Winning Pattern Selection Engine
# Chooses the best matching winning pattern for the current signal

from typing import Dict, List
from wpil_memory import load_patterns


def select_winning_pattern(content_signal: Dict) -> Dict:
    """
    Selects the most relevant winning pattern based on strict matching.
    Priority:
    1. platform
    2. niche
    3. intent
    """

    patterns: List[Dict] = load_patterns()

    if not patterns:
        raise RuntimeError("WPIL has no stored patterns.")

    platform = content_signal.get("platform")
    niche = content_signal.get("niche")
    intent = content_signal.get("intent")

    scored_patterns = []

    for pattern in patterns:
        score = 0

        if pattern.get("platform") == platform:
            score += 3

        if pattern.get("niche") == niche:
            score += 2

        if pattern.get("intent") == intent:
            score += 1

        if score > 0:
            scored_patterns.append((score, pattern))

    if not scored_patterns:
        raise RuntimeError("No compatible winning pattern found.")

    # Choose the highest scoring pattern
    scored_patterns.sort(key=lambda x: x[0], reverse=True)

    return scored_patterns[0][1]
