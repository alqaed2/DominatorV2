import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import settings
from db import SessionLocal, init_db
from models import SessionModel, MetricEvent
from schemas import (
    OnboardRequest,
    DailyBriefRequest,
    BuildPackRequest,
    SubmitMetricsRequest,
)

from services import generator as generator_svc
from services import artifacts as artifacts_svc


VERSION = os.getenv("APP_VERSION", "0.1.0")

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
log = logging.getLogger("dominator")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_error(message: str, code: int = 400, extra: Optional[Dict[str, Any]] = None):
    payload = {"error": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), code


def _db():
    return SessionLocal()


app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": settings.CORS_ORIGINS}},
    supports_credentials=True,
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["600 per hour"],
    storage_uri=settings.RATELIMIT_STORAGE_URI,
)

# Ensure DB schema exists on startup. We *do not* crash the web process if DB is temporarily unavailable;
# endpoints that require DB will surface a clear error, and Render will still detect the open port.
DB_INIT_OK = True
try:
    init_db()
    log.info("DB init: OK")
except Exception:
    DB_INIT_OK = False
    log.exception("DB init failed; continuing without DB")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "version": VERSION, "ts": _iso_now(), "db_ready": DB_INIT_OK})


@app.post("/v1/session")
@limiter.limit("60 per minute")
def post_session():
    """
    Creates a session row used for tracking metrics/onboarding.
    """
    session_id = uuid.uuid4().hex
    db = _db()
    try:
        s = SessionModel(id=session_id, created_at=datetime.now(timezone.utc))
        db.add(s)
        db.commit()
        return jsonify({"session_id": session_id, "created_at": s.created_at.isoformat()})
    except Exception as e:
        db.rollback()
        # Do not crash: return clear error
        log.exception("Failed to create session")
        return _json_error("Failed to create session", 500, {"details": str(e)})
    finally:
        db.close()


@app.post("/v1/onboard")
@limiter.limit("60 per minute")
def post_onboard():
    data = request.get_json(silent=True) or {}
    try:
        payload = OnboardRequest(**data)
    except Exception as e:
        return _json_error("Invalid payload", 400, {"details": str(e)})

    session_id = data.get("session_id")
    if not session_id:
        return _json_error("session_id is required", 400)

    db = _db()
    try:
        s = db.get(SessionModel, session_id)
        if not s:
            return _json_error("Session not found", 404)

        s.project_name = payload.project_name
        s.niche = payload.niche
        s.audience = payload.audience
        s.goal = payload.goal
        s.platforms = ",".join(payload.platforms)
        s.language = payload.language
        s.onboarded_at = datetime.now(timezone.utc)

        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.rollback()
        log.exception("Onboard failed")
        return _json_error("Onboard failed", 500, {"details": str(e)})
    finally:
        db.close()


@app.post("/v1/daily-brief")
@limiter.limit("120 per minute")
def post_daily_brief():
    data = request.get_json(silent=True) or {}
    try:
        payload = DailyBriefRequest(**data)
    except Exception as e:
        return _json_error("Invalid payload", 400, {"details": str(e)})

    brief = generator_svc.generate_daily_brief(payload.idea, payload.language)
    return jsonify({"brief": brief})


@app.post("/v1/generate/variants")
@limiter.limit("120 per minute")
def post_variants():
    data = request.get_json(silent=True) or {}
    idea = (data.get("idea") or "").strip()
    if not idea:
        return _json_error("idea is required", 400)
    language = (data.get("language") or "ar").strip()
    count = int(data.get("count") or 8)

    variants = generator_svc.build_variants_for_idea(idea=idea, count=count, language=language)
    return jsonify({"variants": variants})


@app.post("/v1/artifacts/blueprint")
@limiter.limit("120 per minute")
def post_blueprint():
    data = request.get_json(silent=True) or {}
    idea_title = (data.get("idea_title") or data.get("title") or "").strip()
    angle = (data.get("angle") or "").strip()
    value_promise = (data.get("value_promise") or "").strip()
    video_seconds = int(data.get("video_seconds") or 45)
    language = (data.get("language") or "ar").strip()

    if not idea_title or not angle or not value_promise:
        return _json_error("idea_title/title, angle, and value_promise are required", 400)

    blueprint = artifacts_svc.build_blueprint(
        idea_title=idea_title,
        angle=angle,
        value_promise=value_promise,
        video_seconds=video_seconds,
        language=language,
    )
    kit = artifacts_svc.render_ready_to_record_kit(blueprint=blueprint, language=language)
    return jsonify({"blueprint": blueprint, "kit": kit})


@app.post("/v1/experiments/plan")
@limiter.limit("120 per minute")
def post_experiment_plan():
    data = request.get_json(silent=True) or {}
    try:
        payload = BuildPackRequest(**data)
    except Exception as e:
        return _json_error("Invalid payload", 400, {"details": str(e)})

    plan = artifacts_svc.build_experiment_plan(
        title=payload.title,
        niche=payload.niche,
        goal="",
        platforms=["tiktok", "reels", "shorts"],
        days=7,
        language=payload.language,
    )
    return jsonify({"plan": plan})


@app.post("/v1/prompts/pack")
@limiter.limit("120 per minute")
def post_prompt_pack():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return _json_error("title is required", 400)
    style = (data.get("style") or "cinematic").strip()
    language = (data.get("language") or "ar").strip()

    pack = artifacts_svc.build_prompt_pack(title=title, style=style, outputs=None, language=language)
    return jsonify({"pack": pack})


@app.post("/v1/metrics/submit")
@limiter.limit("240 per minute")
def post_metrics_submit():
    data = request.get_json(silent=True) or {}
    try:
        payload = SubmitMetricsRequest(**data)
    except Exception as e:
        return _json_error("Invalid payload", 400, {"details": str(e)})

    db = _db()
    try:
        s = db.get(SessionModel, payload.session_id)
        if not s:
            return _json_error("Session not found", 404)

        ev = MetricEvent(
            session_id=payload.session_id,
            platform=payload.platform,
            content_id=payload.content_id,
            metrics_json=payload.metrics,
            ts=payload.ts or _iso_now(),
        )
        db.add(ev)
        db.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.rollback()
        log.exception("Metrics submit failed")
        return _json_error("Metrics submit failed", 500, {"details": str(e)})
    finally:
        db.close()


# ---- boot ----
# DB schema initialization already attempted above.

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
