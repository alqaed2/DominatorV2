import os
import json
import uuid
import time
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional, List

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# ملاحظة: هذه imports موجودة في مشروعك (services/*). لا تحذفها.
from services.generator import generate_daily_brief, build_variants_for_idea
from services.blueprint import build_blueprint
from services.renderers import render_ready_to_record_kit, render_experiment_plan, render_prompt_pack


# ---------------------------------------
# App
# ---------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data.sqlite3"))

# مهم: template_folder="templates" لأن index.html داخل templates/
app = Flask(__name__, template_folder="templates")
CORS(app)


# ---------------------------------------
# DB helpers
# ---------------------------------------
def _conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    with _conn() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                creator_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        con.commit()

def _now_iso():
    return datetime.utcnow().isoformat()

def _put_creator(creator_id: str, payload: Dict[str, Any]):
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO creators (creator_id, payload_json, created_at) VALUES (?, ?, ?)",
            (creator_id, json.dumps(payload, ensure_ascii=False), _now_iso()),
        )
        con.commit()

def _get_creator(creator_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT payload_json FROM creators WHERE creator_id = ?", (creator_id,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

def _put_experiment(experiment_id: str, creator_id: str, payload: Dict[str, Any]):
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO experiments (experiment_id, creator_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (experiment_id, creator_id, json.dumps(payload, ensure_ascii=False), _now_iso()),
        )
        con.commit()

def _get_experiment(experiment_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        cur = con.cursor()
        cur.execute("SELECT payload_json FROM experiments WHERE experiment_id = ?", (experiment_id,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None

def _put_metrics(experiment_id: str, creator_id: str, payload: Dict[str, Any]):
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO metrics (id, experiment_id, creator_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), experiment_id, creator_id, json.dumps(payload, ensure_ascii=False), _now_iso()),
        )
        con.commit()

def _list_metrics(experiment_id: str, creator_id: str) -> List[Dict[str, Any]]:
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "SELECT payload_json, created_at FROM metrics WHERE experiment_id = ? AND creator_id = ? ORDER BY created_at ASC",
            (experiment_id, creator_id),
        )
        rows = cur.fetchall()
        out = []
        for (pj, created_at) in rows:
            try:
                out.append({"created_at": created_at, "payload": json.loads(pj)})
            except Exception:
                out.append({"created_at": created_at, "payload": pj})
        return out


# ---------------------------------------
# Health + Home
# ---------------------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "AI_DOMINATOR_TikTok_First"}), 200

@app.route("/", methods=["GET", "HEAD"])
def home():
    """
    - المتصفح: يعرض صفحة HTML (لوحة تحكم) لتجربة الـAPI من داخل المتصفح.
    - أي عميل غير متصفح/بدون text/html: يعرض JSON endpoints (كما كان سابقًا).
    """
    accept = (request.headers.get("Accept") or "").lower()

    # Render يعمل HEAD / للتأكد من الخدمة. نرجع 200 سريعًا.
    if request.method == "HEAD":
        return ("", 200)

    if "text/html" in accept:
        return render_template("index.html")

    return jsonify({
        "status": "ok",
        "service": "AI_DOMINATOR_TikTok_First",
        "endpoints": {
            "onboard": "POST /v1/onboard",
            "daily_brief": "POST /v1/daily-brief",
            "build_pack": "POST /v1/build-pack",
            "submit_metrics": "POST /v1/submit-metrics",
            "report": "GET /v1/report/<experiment_id>?creator_id=...",
            "health": "GET /health",
        }
    }), 200

@app.get("/favicon.ico")
def favicon():
    # لتجنّب 404 في Console
    return ("", 204)


# ---------------------------------------
# API
# ---------------------------------------
@app.post("/v1/onboard")
def onboard():
    payload = request.get_json(silent=True) or {}

    display_name = (payload.get("display_name") or "").strip()
    goal = (payload.get("goal") or "").strip()
    primary_niche = (payload.get("primary_niche") or "").strip()

    language = (payload.get("language") or "ar").strip()
    tone = (payload.get("tone") or "educational").strip()

    sub_niches = payload.get("sub_niches", []) or []
    constraints = payload.get("constraints", {}) or {}

    tiktok_profile_url = payload.get("tiktok_profile_url")
    top_video_urls = payload.get("top_video_urls", []) or []
    weak_video_urls = payload.get("weak_video_urls", []) or []
    past_scripts = payload.get("past_scripts", []) or []

    if not display_name or not goal or not primary_niche:
        return jsonify({"error": "display_name و goal و primary_niche مطلوبة"}), 400

    creator_id = str(uuid.uuid4())

    creator_payload = {
        "creator_id": creator_id,
        "display_name": display_name,
        "goal": goal,
        "primary_niche": primary_niche,
        "sub_niches": sub_niches,
        "language": language,
        "tone": tone,
        "constraints": constraints,
        "tiktok_profile_url": tiktok_profile_url,
        "top_video_urls": top_video_urls,
        "weak_video_urls": weak_video_urls,
        "past_scripts": past_scripts,
        "created_at": _now_iso(),
    }

    _put_creator(creator_id, creator_payload)

    mode_default = "manual"  # حالياً بدون ربط TikTok
    message = "تم إنشاء ملفك بنجاح. الوضع الافتراضي: Manual (بدون ربط TikTok)."

    return jsonify({
        "creator_id": creator_id,
        "message": message,
        "mode_default": "Manual (بدون ربط TikTok).",
        "mode_default_key": mode_default
    }), 200


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

    predicted_scores = {v["key"]: float(v["score"]) for v in variants}
    predicted = {"scores": predicted_scores, "note": "اختبر Hooks A/B/C للحصول على دليل نتيجة (Lift)."}

    blueprint = build_blueprint(
        idea_title=idea_title,
        angle=angle,
        value_promise=value_promise,
        video_seconds=preferred_length_sec,
    )

    vA = next((v for v in variants if v["key"] == "A"), variants[0])

    ready_kit_payload = render_ready_to_record_kit(
        blueprint=blueprint,
        idea_title=idea_title,
        hooks=variants,
        default_variant=vA,
    )

    experiment_plan_payload = render_experiment_plan()
    prompt_pack_payload = render_prompt_pack(
        idea_title=idea_title,
        angle=angle,
        value_promise=value_promise,
        niche=niche,
        video_seconds=preferred_length_sec,
    )

    artifacts = []
    if mode in ("both", "manual", "ready"):
        artifacts.append({"type": "ready_to_record_kit", "payload": ready_kit_payload})
    artifacts.append({"type": "experiment_plan", "payload": experiment_plan_payload})
    artifacts.append({"type": "prompt_pack", "payload": prompt_pack_payload})

    experiment_id = str(uuid.uuid4())
    experiment_payload = {
        "experiment_id": experiment_id,
        "creator_id": creator_id,
        "idea_title": idea_title,
        "angle": angle,
        "value_promise": value_promise,
        "preferred_length_sec": preferred_length_sec,
        "mode": mode,
        "predicted": predicted,
        "artifacts": artifacts,
        "created_at": _now_iso(),
    }
    _put_experiment(experiment_id, creator_id, experiment_payload)

    return jsonify({
        "experiment_id": experiment_id,
        "predicted": predicted,
        "artifacts": artifacts
    }), 200


@app.post("/v1/submit-metrics")
def submit_metrics():
    payload = request.get_json(silent=True) or {}
    creator_id = payload.get("creator_id")
    experiment_id = payload.get("experiment_id")
    metrics = payload.get("metrics", {})

    if not creator_id or not experiment_id:
        return jsonify({"error": "creator_id و experiment_id مطلوبة"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود"}), 404

    exp = _get_experiment(experiment_id)
    if not exp:
        return jsonify({"error": "experiment_id غير موجود"}), 404

    _put_metrics(experiment_id, creator_id, {"metrics": metrics})

    return jsonify({"status": "ok", "message": "تم حفظ المقاييس بنجاح."}), 200


@app.get("/v1/report/<experiment_id>")
def report(experiment_id: str):
    creator_id = request.args.get("creator_id")
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب كـ query param"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود"}), 404

    exp = _get_experiment(experiment_id)
    if not exp:
        return jsonify({"error": "experiment_id غير موجود"}), 404

    metrics_rows = _list_metrics(experiment_id, creator_id)

    return jsonify({
        "experiment": exp,
        "metrics": metrics_rows
    }), 200


# ---------------------------------------
# Entrypoint
# ---------------------------------------
init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
