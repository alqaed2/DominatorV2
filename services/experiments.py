from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Literal
from sqlalchemy.orm import Session

from models import Experiment, Creator
from utils.logging import get_logger, safe_json

log = get_logger("experiments")


@dataclass
class LiftResult:
    winner: str | None
    lift_views: float
    lift_share_rate: float
    lift_engagement_rate: float


def _rates(views: int, likes: int, comments: int, shares: int) -> tuple[float, float]:
    if views <= 0:
        return 0.0, 0.0
    engagement_rate = (likes + comments + shares) / max(1, views)
    share_rate = shares / max(1, views)
    return engagement_rate, share_rate


def _choose_winner(points: list[dict[str, Any]]) -> str | None:
    """
    Winner selection for MVP:
    - uses latest T+24h if exists else T+60m.
    - primary: shares_per_1k
    - secondary: engagement_rate
    """
    if not points:
        return None

    priority = {"T+60m": 1, "T+24h": 2, "T+48h": 3}
    points_sorted = sorted(points, key=lambda p: priority.get(p.get("t_label", "T+60m"), 0))
    latest = points_sorted[-1]

    scores = []
    for key in ["A", "B", "C"]:
        m = latest.get(key)
        if not m:
            continue
        views = int(m["views"])
        shares = int(m["shares"])
        likes = int(m["likes"])
        comments = int(m["comments"])
        er, sr = _rates(views, likes, comments, shares)
        shares_per_1k = (shares / max(1, views)) * 1000.0
        scores.append((key, shares_per_1k, er))

    if not scores:
        return None
    scores.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return scores[0][0]


def create_experiment(
    db: Session,
    creator: Creator,
    idea_title: str,
    blueprint: dict[str, Any],
    variants: dict[str, dict[str, Any]],
    predicted_scores: dict[str, float],
) -> Experiment:
    exp = Experiment(
        creator_id=creator.id,
        status="running",
        idea_title=idea_title,
        blueprint_json=safe_json(blueprint),
        variant_a_json=safe_json(variants["A"]),
        variant_b_json=safe_json(variants["B"]),
        variant_c_json=safe_json(variants["C"]),
        predicted_score_a=float(predicted_scores["A"]),
        predicted_score_b=float(predicted_scores["B"]),
        predicted_score_c=float(predicted_scores["C"]),
        metrics_json="[]",
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def add_metrics_point(
    db: Session,
    exp: Experiment,
    variant_key: Literal["A", "B", "C"],
    point: dict[str, Any],
) -> LiftResult:
    metrics = json.loads(exp.metrics_json or "[]")

    # Find entry for this t_label or create
    t_label = point["t_label"]
    entry = next((x for x in metrics if x.get("t_label") == t_label), None)
    if entry is None:
        entry = {"t_label": t_label, "A": None, "B": None, "C": None}
        metrics.append(entry)

    entry[variant_key] = point

    # Winner determination
    winner = _choose_winner(metrics)

    # Compute lift vs baseline (creator baseline stored on Creator; here we compute lift by comparing to baseline views)
    # For MVP: lift_views = (winner_views - baseline_views) / max(1, baseline_views)
    # But we don't have baseline inside Experiment; computed later in report using creator record.
    exp.metrics_json = safe_json(metrics)
    exp.winner = winner
    if winner:
        exp.status = "completed"

    db.add(exp)
    db.commit()

    return LiftResult(winner=winner, lift_views=exp.lift_views, lift_share_rate=exp.lift_share_rate, lift_engagement_rate=exp.lift_engagement_rate)


def finalize_lift(db: Session, creator: Creator, exp: Experiment) -> LiftResult:
    """
    Computes lift from latest metrics available.
    Updates creator baseline progressively.
    """
    metrics = json.loads(exp.metrics_json or "[]")
    if not exp.winner:
        return LiftResult(None, 0.0, 0.0, 0.0)

    priority = {"T+60m": 1, "T+24h": 2, "T+48h": 3}
    latest = sorted(metrics, key=lambda p: priority.get(p.get("t_label", "T+60m"), 0))[-1]
    m = latest.get(exp.winner)
    if not m:
        return LiftResult(exp.winner, 0.0, 0.0, 0.0)

    views = int(m["views"])
    likes = int(m["likes"])
    comments = int(m["comments"])
    shares = int(m["shares"])
    er, sr = _rates(views, likes, comments, shares)

    # Baseline update (EMA style)
    alpha = 0.2
    if creator.baseline_views <= 0:
        creator.baseline_views = float(views)
    else:
        creator.baseline_views = (1 - alpha) * creator.baseline_views + alpha * float(views)

    if creator.baseline_engagement_rate <= 0:
        creator.baseline_engagement_rate = er
    else:
        creator.baseline_engagement_rate = (1 - alpha) * creator.baseline_engagement_rate + alpha * er

    if creator.baseline_share_rate <= 0:
        creator.baseline_share_rate = sr
    else:
        creator.baseline_share_rate = (1 - alpha) * creator.baseline_share_rate + alpha * sr

    # Lift vs updated baseline (for display, compare against previous baseline would be cleaner; MVP acceptable)
    lift_views = (float(views) - creator.baseline_views) / max(1.0, creator.baseline_views)
    lift_er = (er - creator.baseline_engagement_rate)
    lift_sr = (sr - creator.baseline_share_rate)

    exp.lift_views = float(lift_views)
    exp.lift_engagement_rate = float(lift_er)
    exp.lift_share_rate = float(lift_sr)

    db.add(creator)
    db.add(exp)
    db.commit()

    return LiftResult(exp.winner, float(lift_views), float(lift_sr), float(lift_er))
