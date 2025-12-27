# wpil_memory.py
# WPIL Memory Store
# Stores ONLY abstract winning patterns (no content, no text)

import json
import os
from typing import Dict, List

MEMORY_FILE = "wpil_patterns.json"


def _load_memory() -> List[Dict]:
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_memory(patterns: List[Dict]) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)


def store_pattern(pattern: Dict) -> None:
    """
    Stores a single winning pattern.
    Pattern must be structural ONLY.
    """
    patterns = _load_memory()
    patterns.append(pattern)
    _save_memory(patterns)


def get_patterns(filter_by: Dict = None) -> List[Dict]:
    """
    Retrieves stored patterns.
    Optional filtering by platform / niche / intent.
    """
    patterns = _load_memory()
    if not filter_by:
        return patterns

    filtered = []
    for p in patterns:
        match = True
        for k, v in filter_by.items():
            if p.get(k) != v:
                match = False
                break
        if match:
            filtered.append(p)

    return filtered
