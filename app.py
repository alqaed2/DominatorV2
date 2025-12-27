from __future__ import annotations

import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy.orm import Session

from config import settings
from db import SessionLocal, init_db
from models import Creator, AuditLog
from schemas import (
    OnboardRequest, OnboardResponse,
    DailyBriefRequest, DailyBriefResponse,
    BuildPackRequest, BuildPackResponse,
    SubmitMetricsRequest, SubmitMetricsResponse,
    ReportResponse,
)
from utils.logging import get_logger, safe_json
from services.genome import ensure_genome, seed_creator_dna, update_genome_after_experiment
from services.generator import generate_daily_ideas, build_blueprint, score_variants
from services.artifacts import build_ready_to_record_kit, build_prompt_pack, build_experiment_plan
from services.policy import evaluate_policy
from services.experiments import create_experiment, add_metrics_point, finalize_lift

log = get_logger("app")


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    app.config["MAX_CONTENT_LENGTH"] = settings.MAX_REQUEST_BYTES

    init_db()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "AI_DOMINATOR_TikTok_First", "version": "v1.0-mvp"}

    def db_session() -> Session:
        return SessionLocal()

    def audit(db: Session, creator_id: str | None, event: str, payload: dict, severity: str = "INFO", blocked: bool = False):
        a = AuditLog(creator_id=creator_id, event=event, severity=severity, payload_json=safe_json(payload), blocked=blocked)
        db.add(a)
        db.commit()

    @app.post(f"{settings.API_PREFIX}/onboard")
    def onboard():
        body = request.get_json(force=True, silent=False)
        req = OnboardRequest(**body)
        db = db_session()
        try:
            creator = Creator(
                display_name=req.display_name,
                goal=req.goal,
                primary_niche=req.primary_niche,
                sub_niches=safe_json(req.sub_niches),
                language=req.language,
                tone=req.tone,
                constraints_json=safe_json(req.constraints),
                tiktok_profile_url=req.tiktok_profile_url,
            )
            db.add(creator)
            db.commit()
            db.refresh(creator)

            g = ensure_genome(db, creator)
            dna = seed_creator_dna(creator, req.top_video_urls, req.weak_video_urls, req.past_scripts)
            g.creator_dna_json = safe_json(dna)
            db.add(g)
            db.commit()

            audit(db, creator.id, "creator.onboarded", {"creator": creator.display_name, "goal": creator.goal})

            resp = OnboardResponse(
                creator_id=creator.id,
                message="تم إنشاء ملفك بنجاح. الوضع الافتراضي: Manual (بدون ربط TikTok).",
            )
            return jsonify(resp.model_dump())

        finally:
            db.close()

    @app.post(f"{settings.API_PREFIX}/daily-brief")
    def daily_brief():
        body = request.get_json(force=True, silent=False)
        req = DailyBriefRequest(**body)
        db = db_session()
        try:
            creator = db.get(Creator, req.creator_id)
            if not creator:
                return jsonify({"error": "creator_not_found"}), 404

            creator_dict = {
                "id": creator.id,
                "primary_niche": creator.primary_niche,
                "goal": creator.goal,
                "tone": creator.tone,
                "language": creator.language,
            }

            ideas = generate_daily_ideas(creator_dict, req.competitor_urls)
            out_ideas = []
            for idea in ideas:
                blueprint = build_blueprint(creator_dict, idea["title"], idea["angle"], idea["value_promise"], 28)
                scored = score_variants(blueprint)
                out_ideas.append({
                    "title": idea["title"],
                    "angle": idea["angle"],
                    "value_promise": idea["value_promise"],
                    "variants": [
                        {"key": "A", **scored["A"]},
                        {"key": "B", **scored["B"]},
                        {"key": "C", **scored["C"]},
                    ]
                })

            audit(db, creator.id, "brief.generated", {"ideas": [i["title"] for i in out_ideas]})
            resp = DailyBriefResponse(creator_id=creator.id, ideas=out_ideas)
            return jsonify(resp.model_dump())

        finally:
            db.close()

    @app.post(f"{settings.API_PREFIX}/build-pack")
    def build_pack():
        body = request.get_json(force=True, silent=False)
        req = BuildPackRequest(**body)
        db = db_session()
        try:
            creator = db.get(Creator, req.creator_id)
            if not creator:
                return jsonify({"error": "creator_not_found"}), 404

            constraints = json.loads(creator.constraints_json or "{}")

            creator_dict = {
                "id": creator.id,
                "primary_niche": creator.primary_niche,
                "goal": creator.goal,
                "tone": creator.tone,
                "language": creator.language,
            }

            blueprint = build_blueprint(
                creator_dict,
                req.idea_title,
                req.angle,
                req.value_promise,
                req.preferred_length_sec,
            )

            # Score variants
            variants_scored = score_variants(blueprint)

            # Apply policy gate per variant; if blocked, sanitize
            artifacts = []
            predicted_scores = {}
            variants_for_db = {}
            for key in ["A", "B", "C"]:
                variant = {
                    "hook_text": variants_scored[key]["hook_text"],
                    "onscreen_text": variants_scored[key]["onscreen_text"],
                    "score": variants_scored[key]["score"],
                    "why": variants_scored[key]["why"],
                    "minimum_fix": variants_scored[key]["minimum_fix"],
                }

                # Build a full content object for policy scanning
                content_for_policy = {
                    "script": blueprint["script"].replace("{{HOOK}}", variant["hook_text"]),
                    "caption": blueprint["caption"],
                    "onscreen_text": blueprint["onscreen_srt"].replace("{{HOOK}}", variant["onscreen_text"]),
                }
                decision = evaluate_policy(content_for_policy, constraints)
                audit(db, creator.id, "policy.evaluated", {"variant": key, "allowed": decision.allowed, "reasons": decision.reasons}, blocked=not decision.allowed)

                variants_for_db[key] = variant
                predicted_scores[key] = float(variant["score"])

            # Create experiment record
            exp = create_experiment(db, creator, req.idea_title, blueprint, variants_for_db, predicted_scores)

            # Decide output types
            plan = build_experiment_plan(blueprint)

            # Default kit uses variant A as "record now", but experiment still tracks A/B/C
            kit = build_ready_to_record_kit(req.idea_title, blueprint, variants_for_db["A"])
            prompt_pack = build_prompt_pack(req.idea_title, blueprint)

            if req.mode in ("kit", "both"):
                artifacts.append({"type": "ready_to_record_kit", "payload": kit})
                artifacts.append({"type": "experiment_plan", "payload": plan})
            if req.mode in ("prompt_pack", "both"):
                artifacts.append({"type": "prompt_pack", "payload": prompt_pack})
                if req.mode == "prompt_pack":
                    artifacts.append({"type": "experiment_plan", "payload": plan})

            audit(db, creator.id, "pack.built", {"experiment_id": exp.id, "idea": req.idea_title, "mode": req.mode})

            resp = BuildPackResponse(
                experiment_id=exp.id,
                artifacts=artifacts,
                predicted={"scores": predicted_scores, "note": "اختبر Hooks A/B/C للحصول على دليل نتيجة (Lift)."},
            )
            return jsonify(resp.model_dump())

        finally:
            db.close()

    @app.post(f"{settings.API_PREFIX}/submit-metrics")
    def submit_metrics():
        body = request.get_json(force=True, silent=False)
        req = SubmitMetricsRequest(**body)
        db = db_session()
        try:
            creator = db.get(Creator, req.creator_id)
            if not creator:
                return jsonify({"error": "creator_not_found"}), 404
            exp = db.get(__import__("models").Experiment, req.experiment_id)
            if not exp or exp.creator_id != creator.id:
                return jsonify({"error": "experiment_not_found"}), 404

            point = req.point.model_dump()
            lr = add_metrics_point(db, exp, req.variant_key, point)

            # If completed, finalize lift + update genome
            winner = exp.winner
            lift = {"views": 0.0, "share_rate": 0.0, "engagement_rate": 0.0}

            if winner:
                lr2 = finalize_lift(db, creator, exp)

                # Update genome memory
                genome = ensure_genome(db, creator)
                winner_variant_json = getattr(exp, f"variant_{winner.lower()}_json")
                winner_variant = json.loads(winner_variant_json or "{}")
                update_genome_after_experiment(db, genome, winner_variant, {
                    "lift_views": lr2.lift_views,
                    "lift_share_rate": lr2.lift_share_rate,
                    "lift_engagement_rate": lr2.lift_engagement_rate,
                })

                lift = {"views": lr2.lift_views, "share_rate": lr2.lift_share_rate, "engagement_rate": lr2.lift_engagement_rate}

            audit(db, creator.id, "metrics.submitted", {"experiment": exp.id, "variant": req.variant_key, "t": req.point.t_label, "winner": winner})

            resp = SubmitMetricsResponse(
                experiment_id=exp.id,
                status=exp.status,
                winner=winner,
                lift=lift,
            )
            return jsonify(resp.model_dump())

        finally:
            db.close()

    @app.get(f"{settings.API_PREFIX}/report/<experiment_id>")
    def report(experiment_id: str):
        creator_id = request.args.get("creator_id")
        if not creator_id:
            return jsonify({"error": "creator_id_required"}), 400

        db = db_session()
        try:
            creator = db.get(Creator, creator_id)
            if not creator:
                return jsonify({"error": "creator_not_found"}), 404

            exp = db.get(__import__("models").Experiment, experiment_id)
            if not exp or exp.creator_id != creator.id:
                return jsonify({"error": "experiment_not_found"}), 404

            predicted = {
                "A": exp.predicted_score_a,
                "B": exp.predicted_score_b,
                "C": exp.predicted_score_c,
            }

            lift = {
                "lift_views": exp.lift_views,
                "lift_share_rate": exp.lift_share_rate,
                "lift_engagement_rate": exp.lift_engagement_rate,
                "baseline_views": creator.baseline_views,
                "baseline_share_rate": creator.baseline_share_rate,
                "baseline_engagement_rate": creator.baseline_engagement_rate,
            }

            # Proof artifact (viral internal)
            proof = {
                "title": exp.idea_title,
                "winner": exp.winner,
                "predicted_scores": predicted,
                "lift": lift,
                "share_caption": f"DOMINATOR Proof: Winner={exp.winner} | LiftViews={exp.lift_views:.2%}",
            }

            resp = ReportResponse(
                experiment_id=exp.id,
                creator_id=creator.id,
                status=exp.status,
                winner=exp.winner,
                predicted_scores=predicted,
                lift=lift,
                proof_artifact=proof,
            )
            return jsonify(resp.model_dump())

        finally:
            db.close()

    return app


app = create_app()
