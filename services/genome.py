from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy.orm import Session

from models import Creator, Genome
from utils.logging import get_logger, safe_json

log = get_logger("genome")


def ensure_genome(db: Session, creator: Creator) -> Genome:
    if creator.genome:
        return creator.genome
    g = Genome(creator_id=creator.id, creator_dna_json="{}", calibration_json="{}")
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def seed_creator_dna(creator: Creator, top_videos: list[str], weak_videos: list[str], past_scripts: list[str]) -> dict:
    """
    MVP DNA seeding:
    - We don't scrape TikTok directly here.
    - We seed a structured DNA profile from user inputs.
    """
    dna = {
        "seeded_at": datetime.utcnow().isoformat(),
        "top_video_urls": top_videos,
        "weak_video_urls": weak_videos,
        "past_scripts_count": len(past_scripts),
        "preferences": {
            "tone": creator.tone,
            "language": creator.language,
            "goal": creator.goal,
            "niche": creator.primary_niche,
        },
        "learned": {
            "hook_archetypes": [],
            "pacing": "fast",
            "avg_length_sec": 28,
            "cta_style": "comment_prompt",
        }
    }
    return dna


def update_genome_after_experiment(db: Session, genome: Genome, winner_variant: dict, lift: dict) -> None:
    dna = json.loads(genome.creator_dna_json or "{}")
    learned = dna.setdefault("learned", {})
    # Store winning hook archetype heuristically
    hook = (winner_variant.get("hook_text") or "").strip()
    if hook:
        archetypes = learned.setdefault("hook_archetypes", [])
        archetypes.append({"hook": hook[:120], "lift": lift, "ts": datetime.utcnow().isoformat()})
        archetypes[:] = archetypes[-50:]  # cap history

    genome.creator_dna_json = safe_json(dna)
    genome.updated_at = datetime.utcnow()
    db.add(genome)
    db.commit()
