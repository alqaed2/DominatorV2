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
    by_variant: dict[str, list[dict]] = {}
    for r in metrics_rows:
        k = (r.get("variant_key") or "A").upper()
        by_variant.setdefault(k, []).append(r)

    def pick_row(rows: list[dict], preferred_labels: list[str]) -> Optional[dict]:
        # find first matching t_label
        for label in preferred_labels:
            for rr in rows:
                if (rr.get("t_label") or "") == label:
                    return rr
        # fallback earliest
        return rows[0] if rows else None

    scoreboard = {}
    for variant, rows in by_variant.items():
        early = pick_row(rows, ["T+60m", "T+180m"])
        late = pick_row(rows, ["T+24h", "T+48h"])

        early_c = (early or {}).get("computed") or {}
        late_c = (late or {}).get("computed") or {}

        phase1 = (
            float(early_c.get("views_velocity", 0.0))
            + 300.0 * float(early_c.get("shares_per_1k_views", 0.0))
        )
        phase2 = (
            200.0 * float(late_c.get("comments_per_1k_views", 0.0))
            + 800.0 * float(late_c.get("engagement_rate", 0.0))
        )

        # if late is missing, rely on phase1 only
        if late is None:
            total = phase1
            basis = "phase1_only"
        else:
            total = (0.4 * phase1) + (0.6 * phase2)
            basis = "phase1_phase2"

        scoreboard[variant] = {
            "basis": basis,
            "phase1": phase1,
            "phase2": phase2 if late is not None else None,
            "total": total,
        }

    if not scoreboard:
        return {"winner": None, "scoreboard": {}}

    winner = max(scoreboard.items(), key=lambda kv: kv[1]["total"])[0]
    return {"winner": winner, "scoreboard": scoreboard}


app = Flask(__name__)
app.json.ensure_ascii = False  # important for Arabic output

if CORS:
    CORS(app, resources={r"/*": {"origins": "*"}})

_init_db()


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": APP_NAME, "time": _now_iso()}), 200


@app.get("/")
def root():
    return jsonify(
        {
            "service": APP_NAME,
            "status": "ok",
            "endpoints": {
                "health": "GET /health",
                "onboard": "POST /v1/onboard",
                "daily_brief": "POST /v1/daily-brief",
                "build_pack": "POST /v1/build-pack",
                "submit_metrics": "POST /v1/submit-metrics",
                "report": "GET /v1/report/<experiment_id>?creator_id=...",
            },
        }
    ), 200


@app.post("/v1/onboard")
def onboard():
    payload = request.get_json(silent=True) or {}
    creator_id = str(uuid.uuid4())

    display_name = payload.get("display_name", "Creator")
    goal = payload.get("goal", "followers")
    primary_niche = payload.get("primary_niche", "التسويق الرقمي")
    sub_niches = payload.get("sub_niches", [])
    language = payload.get("language", "ar")
    tone = payload.get("tone", "educational")
    constraints = payload.get("constraints", {})
    tiktok_profile_url = payload.get("tiktok_profile_url", None)

    # TikTok connect is optional: default manual
    mode_default = "manual"

    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO creators (
          creator_id, display_name, goal, primary_niche, sub_niches_json,
          language, tone, constraints_json, tiktok_profile_url, mode_default, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            creator_id,
            display_name,
            goal,
            primary_niche,
            _json_dump(sub_niches),
            language,
            tone,
            _json_dump(constraints),
            tiktok_profile_url,
            mode_default,
            _now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "creator_id": creator_id,
            "message": "تم إنشاء ملفك بنجاح. الوضع الافتراضي: Manual (بدون ربط TikTok).",
            "mode_default": mode_default,
        }
    ), 200


@app.post("/v1/daily-brief")
def daily_brief():
    payload = request.get_json(silent=True) or {}
    creator_id = payload.get("creator_id")
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود"}), 404

    competitor_urls = payload.get("competitor_urls", []) or []
    extra_context = payload.get("extra_context", "") or ""

    ideas = generate_daily_brief(
        primary_niche=creator.get("primary_niche", "التسويق الرقمي"),
        language=creator.get("language", "ar"),
        tone=creator.get("tone", "educational"),
        competitor_urls=competitor_urls,
        extra_context=extra_context,
    )

    return jsonify({"creator_id": creator_id, "ideas": ideas}), 200


@app.post("/v1/build-pack")
def build_pack():
    payload = request.get_json(silent=True) or {}
    creator_id = payload.get("creator_id")
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود"}), 404

    idea_title = (payload.get("idea_title") or "").strip()
    angle = (payload.get("angle") or "").strip()
    value_promise = (payload.get("value_promise") or "").strip()
    preferred_length_sec = int(payload.get("preferred_length_sec") or 28)
    mode = (payload.get("mode") or "both").strip().lower()

    if not idea_title or not angle or not value_promise:
        return jsonify({"error": "idea_title و angle و value_promise مطلوبة"}), 400

    niche = creator.get("primary_niche", "التسويق الرقمي")
    variants = build_variants_for_idea(title=idea_title, angle=angle, niche=niche)

    # predicted scores
    predicted_scores = {v["key"]: float(v["score"]) for v in variants}
    predicted = {
        "scores": predicted_scores,
        "note": "اختبر Hooks A/B/C للحصول على دليل نتيجة (Lift).",
    }

    # blueprint + artifacts
    blueprint = build_blueprint(
        idea_title=idea_title,
        angle=angle,
        value_promise=value_promise,
        video_seconds=preferred_length_sec,
    )

    # choose default variant A for the ready-to-record kit (while still providing hooks A/B/C)
    vA = next((v for v in variants if v["key"] == "A"), variants[0])

    ready_kit_payload = render_ready_to_record_kit(
        blueprint=blueprint,
        selected_hook_text=vA["hook_text"],
        selected_onscreen_text=vA["onscreen_text"],
        hooks_map={
            v["key"]: {"hook_text": v["hook_text"], "onscreen_text": v["onscreen_text"]}
            for v in variants
        },
        keywords=[niche, angle],
    )

    experiment_plan_payload = build_experiment_plan()
    prompt_pack_payload = build_prompt_pack(
        idea_title=idea_title,
        angle=angle,
        value_promise=value_promise,
    )

    artifacts = []
    if mode in ("kit", "both"):
        artifacts.append({"type": "ready_to_record_kit", "payload": ready_kit_payload})
        artifacts.append({"type": "experiment_plan", "payload": experiment_plan_payload})
    if mode in ("prompt_pack", "both"):
        artifacts.append({"type": "prompt_pack", "payload": prompt_pack_payload})

    experiment_id = str(uuid.uuid4())

    conn = _db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO experiments (
          experiment_id, creator_id, idea_title, angle, value_promise,
          preferred_length_sec, mode, artifacts_json, predicted_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            experiment_id,
            creator_id,
            idea_title,
            angle,
            value_promise,
            preferred_length_sec,
            mode,
            _json_dump(artifacts),
            _json_dump(predicted),
            _now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    return jsonify({"experiment_id": experiment_id, "predicted": predicted, "artifacts": artifacts}), 200


@app.post("/v1/submit-metrics")
def submit_metrics():
    payload = request.get_json(silent=True) or {}
    creator_id = payload.get("creator_id")
    experiment_id = payload.get("experiment_id")
    variant_key = (payload.get("variant_key") or "A").strip().upper()
    point = payload.get("point") or {}

    if not creator_id or not experiment_id:
        return jsonify({"error": "creator_id و experiment_id مطلوبان"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود"}), 404

    exp = _get_experiment(experiment_id)
    if not exp or exp.get("creator_id") != creator_id:
        return jsonify({"error": "experiment_id غير موجود أو لا يطابق creator_id"}), 404

    t_label = (point.get("t_label") or payload.get("t_label") or "T+60m").strip()

    computed = _compute_point_scores(point)
    saved = _insert_metric(
        experiment_id=experiment_id,
        creator_id=creator_id,
        variant_key=variant_key,
        t_label=t_label,
        metrics=point,
        computed=computed,
    )

    return jsonify(
        {
            "ok": True,
            "experiment_id": experiment_id,
            "creator_id": creator_id,
            "variant_key": variant_key,
            "t_label": t_label,
            "computed": saved["computed"],
            "metric_id": saved["id"],
        }
    ), 200


@app.get("/v1/report/<experiment_id>")
def report(experiment_id: str):
    creator_id = request.args.get("creator_id", "").strip()
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب في query string"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود"}), 404

    exp = _get_experiment(experiment_id)
    if not exp or exp.get("creator_id") != creator_id:
        return jsonify({"error": "experiment_id غير موجود أو لا يطابق creator_id"}), 404

    rows = _fetch_metrics(experiment_id=experiment_id, creator_id=creator_id)
    decision = _decide_winner(rows)

    # summary by variant
    summary = {}
    for r in rows:
        k = (r.get("variant_key") or "A").upper()
        summary.setdefault(k, []).append(
            {
                "t_label": r.get("t_label"),
                "metrics": r.get("metrics"),
                "computed": r.get("computed"),
                "created_at": r.get("created_at"),
            }
        )

    return jsonify(
        {
            "creator_id": creator_id,
            "experiment_id": experiment_id,
            "idea_title": exp.get("idea_title"),
            "angle": exp.get("angle"),
            "value_promise": exp.get("value_promise"),
            "predicted": exp.get("predicted"),
            "winner": decision.get("winner"),
            "scoreboard": decision.get("scoreboard"),
            "metrics": summary,
        }
    ), 200
