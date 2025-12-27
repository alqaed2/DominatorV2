import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

# Optional: Flask-Cors (installed in your requirements)
try:
    from flask_cors import CORS
except Exception:
    CORS = None

from services.generator import generate_daily_brief, build_variants_for_idea
from services.artifacts import (
    build_blueprint,
    render_ready_to_record_kit,
    build_experiment_plan,
    build_prompt_pack,
)

APP_NAME = "AI_DOMINATOR_TikTok_First"
DB_PATH = os.getenv("DOMINATOR_DB_PATH", "dominator.db")


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS creators (
            creator_id TEXT PRIMARY KEY,
            display_name TEXT,
            goal TEXT,
            primary_niche TEXT,
            sub_niches_json TEXT,
            language TEXT,
            tone TEXT,
            constraints_json TEXT,
            tiktok_profile_url TEXT,
            mode_default TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            creator_id TEXT,
            idea_title TEXT,
            angle TEXT,
            value_promise TEXT,
            preferred_length_sec INTEGER,
            mode TEXT,
            artifacts_json TEXT,
            predicted_json TEXT,
            created_at TEXT,
            FOREIGN KEY(creator_id) REFERENCES creators(creator_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            id TEXT PRIMARY KEY,
            experiment_id TEXT,
            creator_id TEXT,
            variant_key TEXT,
            t_label TEXT,
            metrics_json TEXT,
            computed_json TEXT,
            created_at TEXT,
            FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id),
            FOREIGN KEY(creator_id) REFERENCES creators(creator_id)
        )
        """
    )

    conn.commit()
    conn.close()


def _json_load(s: Optional[str], default):
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def _json_dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _get_creator(creator_id: str) -> Optional[Dict[str, Any]]:
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM creators WHERE creator_id=?", (creator_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["sub_niches"] = _json_load(d.get("sub_niches_json"), [])
    d["constraints"] = _json_load(d.get("constraints_json"), {})
    return d


def _get_experiment(experiment_id: str) -> Optional[Dict[str, Any]]:
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM experiments WHERE experiment_id=?", (experiment_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["artifacts"] = _json_load(d.get("artifacts_json"), [])
    d["predicted"] = _json_load(d.get("predicted_json"), {})
    return d


def _insert_metric(experiment_id: str, creator_id: str, variant_key: str, t_label: str, metrics: dict, computed: dict) -> dict:
    conn = _db()
    cur = conn.cursor()
    metric_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO metrics (id, experiment_id, creator_id, variant_key, t_label, metrics_json, computed_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric_id,
            experiment_id,
            creator_id,
            variant_key,
            t_label,
            _json_dump(metrics),
            _json_dump(computed),
            _now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": metric_id, "computed": computed}


def _fetch_metrics(experiment_id: str, creator_id: str) -> list[dict]:
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM metrics WHERE experiment_id=? AND creator_id=? ORDER BY created_at ASC",
        (experiment_id, creator_id),
    )
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["metrics"] = _json_load(d.get("metrics_json"), {})
        d["computed"] = _json_load(d.get("computed_json"), {})
        out.append(d)
    return out


def _compute_point_scores(point: dict) -> dict:
    # safe numeric parsing
    views = max(int(point.get("views", 0) or 0), 0)
    likes = max(int(point.get("likes", 0) or 0), 0)
    comments = max(int(point.get("comments", 0) or 0), 0)
    shares = max(int(point.get("shares", 0) or 0), 0)
    followers_gained = max(int(point.get("followers_gained", 0) or 0), 0)
    profile_visits = max(int(point.get("profile_visits", 0) or 0), 0)

    engagement = likes + comments + shares
    engagement_rate = (engagement / views) if views > 0 else 0.0
    shares_per_1k = (shares * 1000.0 / views) if views > 0 else 0.0
    comments_per_1k = (comments * 1000.0 / views) if views > 0 else 0.0

    # proxy "velocity" score: views at early checkpoints
    views_velocity = float(views)

    return {
        "views_velocity": views_velocity,
        "shares_per_1k_views": shares_per_1k,
        "comments_per_1k_views": comments_per_1k,
        "engagement_rate": engagement_rate,
        "followers_gained": followers_gained,
        "profile_visits": profile_visits,
    }


def _decide_winner(metrics_rows: list[dict]) -> dict:
    """
    MVP winner decision:
    Phase 1: early growth (views_velocity + shares_per_1k)
    Phase 2: quality (comments_per_1k + engagement_rate)
    If both exist, phase2 has higher weight.
    """
    by_var_
