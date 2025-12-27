PLATFORM_MEMORY = {
    "linkedin": {"successes": 0, "failures": 0},
    "twitter": {"successes": 0, "failures": 0},
    "tiktok": {"successes": 0, "failures": 0},
}

def normalize_platform(p: str) -> str:
    if not p:
        return ""
    p = p.strip().lower()
    if p in {"x", "twitter"}:
        return "twitter"
    return p

def record_success(platform):
    platform = normalize_platform(platform)
    if platform in PLATFORM_MEMORY:
        PLATFORM_MEMORY[platform]["successes"] += 1

def record_failure(platform):
    platform = normalize_platform(platform)
    if platform in PLATFORM_MEMORY:
        PLATFORM_MEMORY[platform]["failures"] += 1

def get_platform_score(platform):
    platform = normalize_platform(platform)
    if platform not in PLATFORM_MEMORY:
        return 0.5

    successes = PLATFORM_MEMORY[platform]["successes"]
    failures = PLATFORM_MEMORY[platform]["failures"]
    total = successes + failures

    if total == 0:
        return 0.5

    return successes / total
