from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from pydantic import ValidationError
from sqlalchemy.orm import Session

from config import settings
from db import SessionLocal, init_db
from models import Creator, Experiment, AuditLog
from schemas import (
    BuildPackRequest,
    OnboardRequest,
    ManualMetricsRequest,
)
from services.generator import GeneratorService
from services.artifacts import ArtifactsService
from services.scoring import ScoringService
from services.experiments import ExperimentsService
from services.trends_provider import trends_bp
from utils.logging import get_logger, safe_json

log = get_logger("app")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.json.ensure_ascii = False
app.json.sort_keys = False
CORS(app)

# Trust Render proxy headers so rate limiting keys use the real client IP.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Basic abuse protection (note: in-memory storage is per-worker; add Redis later for strict global limits).
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[f"{settings.MAX_REQUESTS_PER_IP_PER_MIN}/minute"],
)

app.register_blueprint(trends_bp)

# Ensure DB schema exists at process start. Failing fast is preferable to
# serving a broken UI with 500s (e.g., missing tables / bad DATABASE_URL).
try:
    init_db()
    log.info("DB schema ensured")
except Exception:
    log.exception("DB init failed")
    raise


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> Session:
    return SessionLocal()


def _json_error(message: str, *, status: int = 400, details: Any = None):
    payload: Dict[str, Any] = {"error": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def _payload_guard() -> Optional[Tuple[Any, int]]:
    # Render/Gunicorn might not always set Content-Length.
    if request.content_length is not None and request.content_length > settings.MAX_REQUEST_BYTES:
        return _json_error(
            f"Payload too large (>{settings.MAX_REQUEST_BYTES} bytes)",
            status=413,
        )
    return None


def _audit(db: Session, *, creator_id: Optional[str], event: str, payload: Any, severity: str = "INFO", blocked: bool = False):
    try:
        db.add(
            AuditLog(
                creator_id=creator_id,
                event=event,
                severity=severity,
                payload_json=safe_json(payload),
                blocked=blocked,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Audit log insert failed")


def _create_creator(
    db: Session,
    *,
    display_name: str = "New Creator",
    language: str = "en",
    primary_niche: str = "general",
    goal: str = "followers",
    tone: str = "educational",
) -> Creator:
    c = Creator(
        display_name=display_name,
        goal=goal,
        primary_niche=primary_niche,
        # models.Creator stores sub_niches as a JSON string.
        sub_niches="[]",
        language=language,
        tone=tone,
        constraints_json="{}",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _get_creator(db: Session, creator_id: str) -> Optional[Creator]:
    # Creator IDs are UUID strings (see models.Creator.id).
    creator_id = (creator_id or "").strip()
    if not creator_id:
        return None
    return db.get(Creator, creator_id)


def _best_variant(variants: Dict[str, Dict[str, Any]]) -> str:
    best = "A"
    best_score = -1.0
    for k in ["A", "B", "C"]:
        v = variants.get(k) or {}
        s = float(v.get("score") or 0.0)
        if s > best_score:
            best_score = s
            best = k
    return best


def _time_bucket(hour: int) -> str:
    if 5 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 16:
        return "day"
    if 17 <= hour <= 21:
        return "evening"
    return "night"


def _build_caption(
    *,
    lang: str,
    title: str,
    value_promise: Optional[str] = None,
    country: Optional[str] = None,
    publish_hour_local: Optional[int] = None,
    cta_keyword: Optional[str] = None,
) -> str:
    """Deterministic, production-safe caption builder.

    If country/time is missing, it still produces a strong caption.
    """
    title = (title or "").strip()
    value_promise = (value_promise or "").strip()
    country = (country or "").strip().upper() or None

    # Time-of-day framing
    tod = None
    if publish_hour_local is not None:
        try:
            h = int(publish_hour_local)
            tod = _time_bucket(h)
        except Exception:
            tod = None

    # Micro personalization
    if lang.startswith("ar"):
        openers = {
            "morning": "صباح الإنتاجية:",
            "day": "خلّينا نختصرها:",
            "evening": "قبل ما يخلص اليوم:",
            "night": "آخر الليل، فكرة مجنونة:",
        }
        opener = openers.get(tod or "", "خلّينا ندخل في الزبدة:")
        cta = cta_keyword or "اكتب رأيك"
        location = f" ({country})" if country else ""
        if value_promise:
            return f"{opener} {title}{location}\n{value_promise}\n— {cta} 👇"
        return f"{opener} {title}{location}\n— {cta} 👇"
    else:
        openers = {
            "morning": "Morning boost:",
            "day": "Quick breakdown:",
            "evening": "Before the day ends:",
            "night": "Late-night idea:",
        }
        opener = openers.get(tod or "", "Quick breakdown:")
        cta = cta_keyword or "Comment your take"
        location = f" ({country})" if country else ""
        if value_promise:
            return f"{opener} {title}{location}\n{value_promise}\n— {cta} ↓"
        return f"{opener} {title}{location}\n— {cta} ↓"


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "at": _iso_now()})


@app.get("/v1/session")
def get_session():
    creator_id = request.args.get("creator_id") or ""
    if not creator_id:
        return _json_error("creator_id is required", status=400)
    db = _db()
    try:
        c = _get_creator(db, creator_id)
        if not c:
            return _json_error("creator not found", status=404)
        return jsonify({"creator_id": str(c.id), "profile": {"display_name": c.display_name}})
    finally:
        db.close()


@app.post("/v1/session")
def post_session():
    db = _db()
    try:
        c = _create_creator(db, display_name="Browser Session")
        return jsonify({"creator_id": str(c.id), "message": "ok"})
    finally:
        db.close()


@app.post("/v1/onboard")
def onboard():
    db = _db()
    try:
        data = request.get_json(silent=True) or {}
        try:
            req = OnboardRequest(**data)
        except ValidationError as e:
            return _json_error("validation_error", status=422, details=e.errors())

        # Create a new creator profile
        c = _create_creator(
            db,
            display_name=req.display_name or "New Creator",
            language=req.language or "ar",
            primary_niche=req.primary_niche or "general",
            goal=req.goal or "followers",
            tone=req.tone or "educational",
        )

        # Update optional sub_niches + constraints
        c.sub_niches = safe_json(req.sub_niches)
        c.constraints_json = safe_json(req.constraints or {})
        db.add(c)
        db.commit()

        return jsonify({"creator_id": str(c.id), "message": "created"})
    finally:
        db.close()


@app.post("/v1/build-pack")
@limiter.limit("30/minute")
def build_pack():
    guard = _payload_guard()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    try:
        req = BuildPackRequest(**data)
    except ValidationError as e:
        return _json_error("validation_error", status=422, details=e.errors())

    db = _db()
    try:
        c = _get_creator(db, req.creator_id)
        if not c:
            return _json_error("creator not found", status=404)

        gen = GeneratorService()
        scorer = ScoringService()
        artifacts_svc = ArtifactsService()
        exp_svc = ExperimentsService()

        # Generate candidates
        variants_list = gen.generate_variants(
            idea_title=req.idea_title,
            angle=req.angle,
            niche=c.primary_niche,
        )
        variants = {v["key"]: v for v in variants_list}
        predicted_scores = {k: float((variants.get(k) or {}).get("score") or 0.0) for k in ["A", "B", "C"]}

        # Deterministic blueprint + ready-to-record kit
        blueprint = artifacts_svc.build_blueprint(req.idea_title, req.angle, req.value_promise, req.preferred_length_sec)
        best_key = _best_variant(variants)
        best = variants.get(best_key) or {}
        kit = artifacts_svc.render_ready_to_record_kit(
            blueprint=blueprint,
            selected_hook_text=str(best.get("hook_text") or "").strip(),
            selected_onscreen_text=str(best.get("onscreen_text") or "").strip(),
            hooks_map={k: {"hook_text": (variants.get(k) or {}).get("hook_text"), "onscreen_text": (variants.get(k) or {}).get("onscreen_text")} for k in ["A", "B", "C"]},
            keywords=[w for w in (req.idea_title.split() if req.idea_title else [])[:6]],
        )

        # Caption upgrade (country/time aware, deterministic)
        kit["caption"] = _build_caption(
            lang=c.language,
            title=req.idea_title,
            value_promise=req.value_promise,
            country=req.audience_country,
            publish_hour_local=req.publish_hour_local,
            cta_keyword=req.cta_keyword,
        )

        # Optional scoring mode
        score_payload = None
        if req.mode in ("score", "both"):
            score_payload = scorer.score_pack(
                idea_title=req.idea_title,
                angle=req.angle,
                niche=c.primary_niche,
                variants=variants,
            )

        # Store experiment
        exp = exp_svc.create_experiment(
            db=db,
            creator_id=str(c.id),
            idea_title=req.idea_title,
            angle=req.angle,
            niche=c.primary_niche,
            mode=req.mode,
            variants=variants,
            predicted_scores=predicted_scores,
        )

        _audit(
            db,
            creator_id=str(c.id),
            event="build_pack",
            payload={
                "experiment_id": exp.id,
                "mode": req.mode,
                "idea_title": req.idea_title,
                "angle": req.angle,
            },
        )

        return jsonify(
            {
                "creator_id": str(c.id),
                "experiment_id": exp.id,
                "variants": variants,
                "predicted_scores": predicted_scores,
                "ready_to_record_kit": kit,
                "score": score_payload,
            }
        )
    except Exception as e:
        _audit(
            db,
            creator_id=req.creator_id if "req" in locals() else None,
            event="build_pack_error",
            payload={"error": str(e)},
            severity="ERROR",
        )
        log.exception("build_pack failed")
        return _json_error("internal_error", status=500)
    finally:
        db.close()


@app.post("/v1/metrics/manual")
@limiter.limit("60/minute")
def manual_metrics():
    data = request.get_json(silent=True) or {}
    try:
        req = ManualMetricsRequest(**data)
    except ValidationError as e:
        return _json_error("validation_error", status=422, details=e.errors())

    db = _db()
    try:
        exp = db.get(Experiment, req.experiment_id)
        if not exp:
            return _json_error("experiment not found", status=404)

        # Append snapshot
        try:
            lst = json.loads(exp.metrics_json or "[]")
        except Exception:
            lst = []
        lst.append(
            {
                "at": _iso_now(),
                "label": req.label,
                "views": req.views,
                "likes": req.likes,
                "comments": req.comments,
                "shares": req.shares,
                "avg_watch_time": req.avg_watch_time,
                "completion_rate": req.completion_rate,
            }
        )
        exp.metrics_json = safe_json(lst)
        db.add(exp)
        db.commit()

        _audit(
            db,
            creator_id=exp.creator_id,
            event="manual_metrics",
            payload={"experiment_id": exp.id, "label": req.label},
        )

        return jsonify({"ok": True})
    finally:
        db.close()


# As a safety net for environments that import the module without running the earlier init block.
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
