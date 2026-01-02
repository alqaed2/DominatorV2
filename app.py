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
from models import Creator, Experiment
from schemas import (
    BuildPackRequest,
    DailyBriefRequest,
    MetricsPoint,
    OnboardRequest,
    SubmitMetricsRequest,
)
from services import artifacts as artifacts_svc
from services import experiments as experiments_svc
from services import generator as generator_svc
from services import genome as genome_svc
from services.policy import evaluate_policy
from services.trends_api import trends_bp
from services.trends_provider import get_trends_provider
from utils.logging import get_logger, safe_json


VERSION = "DominatorV2 (Flask) — CEO/CTO Stabilized"
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


@app.before_request
def _before_request():
    guarded = _payload_guard()
    if guarded is not None:
        return guarded
    return None


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    return ("", 204)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "version": VERSION, "ts": _iso_now()})


@app.get("/api")
def api_index():
    return jsonify(
        {
            "name": "DominatorV2",
            "version": VERSION,
            "endpoints": {
                "health": "GET /health",
                "session": "GET|POST /v1/session",
                "onboard": "POST /v1/onboard",
                "daily_brief": "POST /v1/daily-brief",
                "build_pack": "POST /v1/build-pack",
                "trending_hashtags": "POST /v1/trending-hashtags",
                "submit_metrics": "POST /v1/submit-metrics",
                "report": "GET /v1/report/<experiment_id>",
            },
        }
    )


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
        sub_niches_json="[]",
        language=language,
        tone=tone,
        constraints_json="{}",
        tiktok_profile_url=None,
        baseline_views=0.0,
        baseline_engagement_rate=0.0,
        baseline_share_rate=0.0,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    genome_svc.ensure_genome(db, c)
    return c


def _get_creator(db: Session, creator_id: str) -> Optional[Creator]:
    try:
        cid = int(creator_id)
    except Exception:
        return None
    return db.get(Creator, cid)


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


def _build_caption(
    *,
    lang: str,
    title: str,
    value_promise: str,
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
            if 5 <= h <= 10:
                tod = "morning"
            elif 11 <= h <= 16:
                tod = "day"
            elif 17 <= h <= 21:
                tod = "evening"
            else:
                tod = "night"
        except Exception:
            tod = None

    kw = (cta_keyword or "").strip() or ("خطة" if lang == "ar" else "PLAN")

    if lang == "ar":
        lead = {
            "morning": "قبل ما يبدأ يومك…",
            "day": "لو تبغى نتيجة اليوم…",
            "evening": "قبل ما تقفل يومك…",
            "night": "إذا أنت صاحي الآن…",
        }.get(tod, "")
        loc = f" ({country})" if country else ""
        body = f"{title}{loc}\n{value_promise}"
        cta = f"\n\nاكتب كلمة ({kw}) بالتعليقات إذا تبغى النسخة المختصرة."  # purposeful CTA
        return (lead + "\n" if lead else "") + body + cta

    # default: English
    lead = {
        "morning": "Before your day starts…",
        "day": "If you want results today…",
        "evening": "Before you end your day…",
        "night": "If you’re still awake…",
    }.get(tod, "")
    loc = f" ({country})" if country else ""
    body = f"{title}{loc}\n{value_promise}"
    cta = f"\n\nComment '{kw}' and I’ll send you the short version."  # purposeful CTA
    return (lead + "\n" if lead else "") + body + cta


def _build_veo3_prompt(kit: Dict[str, Any], *, lang: str = "en") -> str:
    """High-signal VEO3 prompt with explicit camera/lighting/audio guidance.

    Output is segmented ~8s chunks to match the UI’s card-based copying.
    """
    timeline = kit.get("timeline") or {}
    secs = int(timeline.get("video_seconds") or 28)
    sections = timeline.get("sections") or []

    # Pull a short VO line per section from the teleprompter (best-effort)
    tele = (kit.get("script_teleprompter") or "").strip()
    tele_lines = [ln.strip() for ln in tele.splitlines() if ln.strip()]
    vo_seed = " ".join(tele_lines[:6])[:220]

    # Base style (safe, brandable)
    if lang == "ar":
        base = (
            "إخراج فيديو عمودي 9:16، واقعي سينمائي، إضاءة نظيفة، جودة عالية. "
            "كاميرا: 24–35mm، عمق مجال خفيف، حركة بسيطة (handheld micro-movement). "
            "ألوان محايدة، تباين متوسط. لا تضع نصوص أو شعارات داخل الفيديو (سأضيفها في المونتاج). "
            "الصوت: Voice-over عربي واضح + موسيقى خلفية خفيفة منخفضة + SFX خفيف للنقرات والانتقالات."
        )
        seg_label = "المقطع"
        vo_label = "VO"
    else:
        base = (
            "Vertical 9:16, realistic cinematic look, clean studio lighting, high clarity. "
            "Camera: 24–35mm, mild depth of field, subtle handheld micro-movement. "
            "Neutral color grade, medium contrast. No on-video text or logos (added in post). "
            "Audio: clear voice-over + low background music + light UI click/transition SFX."
        )
        seg_label = "Segment"
        vo_label = "VO"

    def bucket(t0: int) -> Tuple[int, int]:
        t1 = min(secs, t0 + 8)
        return t0, t1

    # Build 0-8, 8-16, 16-24, 24-end
    parts = []
    for t0 in range(0, secs, 8):
        a, b = bucket(t0)
        # Map to timeline section type best-effort
        focus = "hook" if a == 0 else "solution" if a <= 16 else "cta" if b >= secs else "problem"
        if lang == "ar":
            focus_txt = {
                "hook": "لقطة افتتاحية قوية: وجه/منتج في مركز الكادر، تعبير واثق، قطع سريع بعد 1.5 ثانية.",
                "problem": "عرض المشكلة بمثال بصري بسيط (B-roll سريع) مع إبقاء المتحدث في الإطار.",
                "solution": "شرح الخطوات مع تغييرات لقطة/زووم كل 1.5–2 ثانية + B-roll مطابق.",
                "cta": "لقطة ختام ثابتة، نظرة للكاميرا، إشارة يد بسيطة، إيقاع هادئ.",
            }[focus]
            cam = {
                "hook": "حركة: push-in خفيف، تركيز على العينين.",
                "problem": "حركة: pan بسيط لقطع المشهد.",
                "solution": "حركة: jump-cuts محسوبة + لقطة كتف/يدين.",
                "cta": "حركة: ثابت + تباطؤ بسيط في النهاية.",
            }[focus]
        else:
            focus_txt = {
                "hook": "Strong opener: face/product centered, confident expression, quick cut at ~1.5s.",
                "problem": "Show the problem with simple visual example (fast B-roll) while keeping speaker present.",
                "solution": "Explain steps with shot changes/zoom every 1.5–2s + matching B-roll.",
                "cta": "Stable closing shot, direct eye contact, minimal gesture, calmer pacing.",
            }[focus]
            cam = {
                "hook": "Movement: subtle push-in, eye focus.",
                "problem": "Movement: gentle pan to refresh scene.",
                "solution": "Movement: controlled jump cuts + over-shoulder / hands insert.",
                "cta": "Movement: locked-off, slight ease-out at the end.",
            }[focus]

        vo = vo_seed
        parts.append(
            f"[{seg_label} {a:02d}-{b:02d}s]\n"
            f"{base}\n"
            f"{focus_txt} {cam}\n"
            f"{vo_label}: {vo}\n"
        )

    return "\n".join(parts).strip()


@app.get("/v1/session")
def get_session():
    creator_id = (request.args.get("creator_id") or "").strip()
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
            return _json_error("invalid payload", status=422, details=json.loads(e.json()))

        c = _create_creator(
            db,
            display_name=req.display_name,
            language=req.language,
            primary_niche=req.primary_niche,
            goal=req.goal,
            tone=req.tone,
        )
        c.sub_niches_json = safe_json(req.sub_niches)
        c.constraints_json = safe_json(req.constraints)
        c.tiktok_profile_url = req.tiktok_profile_url
        db.add(c)
        db.commit()
        db.refresh(c)

        # Seed DNA
        genome = genome_svc.ensure_genome(db, c)
        dna = genome_svc.seed_creator_dna(c, req.top_video_urls, req.weak_video_urls, req.past_scripts)
        genome.creator_dna_json = safe_json(dna)
        db.add(genome)
        db.commit()

        return jsonify({"creator_id": str(c.id), "mode_default": "manual", "message": "onboarded"})
    finally:
        db.close()


@app.post("/v1/daily-brief")
def daily_brief():
    db = _db()
    try:
        data = request.get_json(silent=True) or {}
        try:
            req = DailyBriefRequest(**data)
        except ValidationError as e:
            return _json_error("invalid payload", status=422, details=json.loads(e.json()))

        c = _get_creator(db, req.creator_id)
        if not c:
            return _json_error("creator not found", status=404)

        ideas = generator_svc.generate_daily_brief(
            primary_niche=c.primary_niche,
            language=c.language,
            tone=c.tone,
            competitor_urls=req.competitor_urls,
            extra_context=req.extra_context or "",
        )
        return jsonify({"creator_id": str(c.id), "ideas": ideas})
    finally:
        db.close()


@app.post("/v1/build-pack")
def build_pack():
    db = _db()
    try:
        data = request.get_json(silent=True) or {}

        # Compatibility: UI may send mode=manual
        if isinstance(data, dict) and data.get("mode") == "manual":
            data = dict(data)
            data["mode"] = "kit"

        # Optional convenience fields (not required by UI today)
        lang = (data.get("language") or "").strip() or None
        country = (data.get("audience_country") or data.get("country") or "").strip() or None
        publish_hour = data.get("publish_hour_local")

        try:
            req = BuildPackRequest(**data)
        except ValidationError as e:
            return _json_error("invalid payload", status=422, details=json.loads(e.json()))

        c = _get_creator(db, req.creator_id)
        if not c:
            return _json_error("creator not found", status=404)

        if lang:
            c.language = lang
            db.add(c)
            db.commit()

        # Build variants A/B/C (heuristic MVP)
        variants_list = generator_svc.build_variants_for_idea(
            title=req.idea_title,
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
            country=country,
            publish_hour_local=publish_hour if publish_hour is None else int(publish_hour),
            cta_keyword="خطة" if c.language == "ar" else "PLAN",
        )

        # Hashtags: prefer trends provider if configured, else keep kit fallback
        try:
            provider = get_trends_provider()
            tr = provider.get_hashtags(
                creator_id=str(c.id),
                limit=12,
                lang=c.language,
                topic=(req.idea_title or c.primary_niche),
            )
            kit["hashtags"] = tr.hashtags
            kit["hashtags_meta"] = {"source": tr.source, "updated_at": tr.updated_at}
        except Exception as e:
            log.warning("trends provider failed: %s", e)

        # VEO3 prompt (server-side, higher quality)
        kit["veo3_prompt"] = _build_veo3_prompt(kit, lang=c.language)

        # Policy gate
        decision = evaluate_policy(
            {
                "script": kit.get("script_teleprompter"),
                "caption": kit.get("caption"),
                "onscreen_text": kit.get("onscreen_text_srt"),
            },
            constraints=json.loads(c.constraints_json or "{}"),
        )
        if not decision.allowed:
            kit["policy_blocked"] = True
            kit["policy_reasons"] = decision.reasons
            # keep sanitized caption/script
            kit["script_teleprompter"] = decision.sanitized.get("script", kit.get("script_teleprompter"))
            kit["caption"] = decision.sanitized.get("caption", kit.get("caption"))

        # Create Experiment row
        exp = experiments_svc.create_experiment(
            db,
            creator=c,
            idea_title=req.idea_title,
            blueprint=blueprint,
            variants={
                "A": variants.get("A") or {},
                "B": variants.get("B") or {},
                "C": variants.get("C") or {},
            },
            predicted_scores=predicted_scores,
        )

        artifacts = []
        if req.mode in ("kit", "both"):
            artifacts.append({"type": "ready_to_record_kit", "payload": kit})
            artifacts.append({"type": "experiment_plan", "payload": artifacts_svc.build_experiment_plan()})
        if req.mode in ("prompt_pack", "both"):
            artifacts.append({"type": "prompt_pack", "payload": artifacts_svc.build_prompt_pack(req.idea_title, req.angle, req.value_promise)})

        return jsonify(
            {
                "experiment_id": str(exp.id),
                "artifacts": artifacts,
                "predicted": {
                    "scores": predicted_scores,
                    "best_variant": best_key,
                    "dominance_band": "+10% to +25%" if max(predicted_scores.values() or [0]) >= 75 else "+0% to +10%",
                },
            }
        )
    finally:
        db.close()


@app.post("/v1/submit-metrics")
def submit_metrics():
    db = _db()
    try:
        data = request.get_json(silent=True) or {}
        try:
            req = SubmitMetricsRequest(**data)
        except ValidationError as e:
            return _json_error("invalid payload", status=422, details=json.loads(e.json()))

        c = _get_creator(db, req.creator_id)
        if not c:
            return _json_error("creator not found", status=404)

        exp = db.get(Experiment, int(req.experiment_id))
        if not exp or exp.creator_id != c.id:
            return _json_error("experiment not found", status=404)

        # pydantic already validated the structure
        point: Dict[str, Any] = json.loads(MetricsPoint(**req.point.model_dump()).model_dump_json())  # type: ignore
        lift = experiments_svc.add_metrics_point(db, exp, req.variant_key, point)

        # If completed, finalize lift + update genome
        if exp.status == "completed" and exp.winner:
            lift2 = experiments_svc.finalize_lift(db, c, exp)
            genome = genome_svc.ensure_genome(db, c)
            winner_variant = json.loads(getattr(exp, f"variant_{exp.winner.lower()}_json") or "{}")
            genome_svc.update_genome_after_experiment(
                db,
                genome,
                winner_variant=winner_variant,
                lift={"lift_views": lift2.lift_views, "lift_share_rate": lift2.lift_share_rate, "lift_engagement_rate": lift2.lift_engagement_rate},
            )

        return jsonify(
            {
                "experiment_id": str(exp.id),
                "status": exp.status,
                "winner": exp.winner,
                "lift": {
                    "lift_views": exp.lift_views,
                    "lift_share_rate": exp.lift_share_rate,
                    "lift_engagement_rate": exp.lift_engagement_rate,
                },
            }
        )
    finally:
        db.close()


@app.get("/v1/report/<experiment_id>")
def report(experiment_id: str):
    db = _db()
    try:
        try:
            eid = int(experiment_id)
        except Exception:
            return _json_error("invalid experiment id", status=400)

        exp = db.get(Experiment, eid)
        if not exp:
            return _json_error("experiment not found", status=404)

        return jsonify(
            {
                "experiment_id": str(exp.id),
                "creator_id": str(exp.creator_id),
                "status": exp.status,
                "winner": exp.winner,
                "predicted_scores": {
                    "A": exp.predicted_score_a,
                    "B": exp.predicted_score_b,
                    "C": exp.predicted_score_c,
                },
                "lift": {
                    "lift_views": exp.lift_views,
                    "lift_share_rate": exp.lift_share_rate,
                    "lift_engagement_rate": exp.lift_engagement_rate,
                },
                "proof_artifact": {
                    "idea_title": exp.idea_title,
                    "winner": exp.winner,
                    "score_before": max(exp.predicted_score_a, exp.predicted_score_b, exp.predicted_score_c),
                    "lift_views": exp.lift_views,
                },
            }
        )
    finally:
        db.close()


# ---- boot ----
init_db()


if __name__ == "__main__":
    # Local dev only. Render uses gunicorn.
    app.run(host="0.0.0.0", port=10000, debug=(settings.ENV != "production"))
