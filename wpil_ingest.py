# wpil_ingest.py
# Controlled Pattern Ingestion Pipeline
# Inserts ONLY abstract winning patterns into WPIL memory

from wpil_memory import store_pattern


def ingest_pattern(pattern: dict) -> None:
    """
    Validates and stores a winning pattern.
    This function is the ONLY allowed entry point to WPIL memory.
    """

    required_fields = [
        "platform",
        "niche",
        "intent",
        "hook",
        "structure",
        "cta"
    ]

    for field in required_fields:
        if field not in pattern:
            raise ValueError(f"Missing required field: {field}")

    # Enforce structural purity
    forbidden_keys = [
        "text",
        "content",
        "post",
        "caption",
        "sentiment",
        "tone",
        "emotion"
    ]

    for key in forbidden_keys:
        if key in pattern:
            raise ValueError(f"Forbidden key detected: {key}")

    store_pattern(pattern)


if __name__ == "__main__":
    # Example controlled ingestion (manual trigger)

    example_pattern = {
        "platform": "linkedin",
        "niche": "leadership",
        "intent": "authority",

        "hook": {
            "type": "bold_claim",
            "max_words": 10
        },

        "structure": {
            "line_density": "one_idea_per_line",
            "sentence_length": "short",
            "narrative_arc": "problem_to_insight"
        },

        "cta": {
            "type": "curiosity",
            "position": "final_line"
        }
    }

    ingest_pattern(example_pattern)
    print("✅ Pattern ingested successfully.")
