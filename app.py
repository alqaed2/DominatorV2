# app.py
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request, send_from_directory

from config import settings
from db import init_db, SessionLocal, engine
from models import Job, Pack
from tasks import process_build_pack, worker_tick


app = Flask(__name__, static_folder="static", static_url_path="/static")


# -------------------------------
# Boot
# -------------------------------

def _boot() -> None:
    # Create tables if missing
    init_db()

_boot()


# -------------------------------
# Helpers
# -------------------------------

def _now() -> datetime:
    return datetime.utcnow()


def _client_ip() -> str:
    # Render provides X-Forwarded-For
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


# Simple per-IP limiter for build-pack only
_REQ_LOG: Dict[str, deque] = defaultdict(deque)


def _rate_limit_ok(ip: str) -> (bool, int):
    limit = int(getattr(settings, "MAX_REQUESTS_PER_IP_PER_MIN", 30) or 30)
    window = 60
    now = time.time()
    q = _REQ_LOG[ip]
    while q and (now - q[0]) > window:
        q.popleft()
    if len(q) >= limit:
        retry_after = int(window - (now - q[0]))
        return False, max(1, retry_after)
    q.append(now)
    return True, 0


def _cleanup_stale_running(db) -> int:
    """
    Critical: never allow running jobs to live forever.
    Any running job older than STALE_SEC is failed.
    """
    stale_sec = max(180, int(getattr(settings, "MODEL_TIMEOUT_SEC", 45) or 45) * 3)
    cutoff = _now() - timedelta(seconds=stale_sec)

    # started_at may be NULL in some legacy rows; fallback to updated_at/created_at
    q = (
        db.query(Job)
        .filter(Job.status == "running")
        .filter((Job.started_at != None) & (Job.started_at < cutoff) | (Job.started_at == None) & (Job.updated_at < cutoff))
    )
    n = q.count()
    if n:
        q.update(
            {
                Job.status: "failed",
                Job.error_message: f"stale_timeout>{stale_sec}s",
                Job.finished_at: _now(),
            },
            synchronize_session=False,
        )
    return n


def _count_status(db, status: str) -> int:
    return db.query(Job).filter(Job.status == status).count()


def _spawn_job(job_id: str) -> None:
    def _runner():
        process_build_pack(job_id)

    t = threading.Thread(target=_runner, name=f"job-{job_id}", daemon=True)
    t.start()


def _kick_scheduler(max_to_start: int = 2) -> Dict[str, Any]:
    """
    Opportunistic scheduler:
    - cleanup stale running
    - start queued jobs up to MAX_CONCURRENT_JOBS
    - atomic claim to avoid duplicates across gunicorn workers
    """
    db = SessionLocal()
    try:
        cleaned = _cleanup_stale_running(db)
        db.commit()

        running = _count_status(db, "running")
        max_running = int(getattr(settings, "MAX_CONCURRENT_JOBS", 2) or 2)
        available = max(0, max_running - running)
        available = min(available, max(1, int(max_to_start or 1)))

        if available <= 0:
            return {"ok": True, "cleaned": cleaned, "started": 0, "running": running}

        # Backlog guard (optional)
        backlog_cap = int(getattr(settings, "MAX_QUEUE_BACKLOG", 30) or 30)
        queued = _count_status(db, "queued")
        if queued > backlog_cap:
            return {"ok": True, "cleaned": cleaned, "started": 0, "running": running, "queued": queued, "backlog_cap": backlog_cap}

        # Select oldest queued
        jobs = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at.asc())
            .limit(available)
            .all()
        )

        started = 0
        for j in jobs:
            # Atomic claim: only start if still queued
            updated = (
                db.query(Job)
                .filter(Job.id == j.id, Job.status == "queued")
                .update(
                    {
                        Job.status: "running",
                        Job.started_at: _now(),
                        Job.progress: 0.05,
                    },
                    synchronize_session=False,
                )
            )
            if updated:
                started += 1
                db.commit()
                _spawn_job(j.id)

        running2 = _count_status(db, "running")
        return {"ok": True, "cleaned": cleaned, "started": started, "running": running2}
    finally:
        db.close()


# -------------------------------
# Web / Health
# -------------------------------

@app.get("/")
def home():
    # Serve templates without Jinja dependency (keep simple)
    return send_from_directory("templates", "index.html")


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "AI-DOMINATOR", "ts": _now().isoformat() + "Z"})


@app.get("/readyz")
def readyz():
    db_ok = True
    err = None
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        db_ok = False
        err = str(e)
    return jsonify({"ready": db_ok, "db_init": True, "db_init_err": err})


# -------------------------------
# API
# -------------------------------

@app.get("/v1/trending-hashtags")
def trending_hashtags():
    # Safe fallback (you can wire Apify later without breaking)
    items = [
        {"tag": "#AI", "score": 98},
        {"tag": "#Marketing", "score": 92},
        {"tag": "#LinkedIn", "score": 90},
        {"tag": "#TikTok", "score": 88},
        {"tag": "#Startups", "score": 86},
        {"tag": "#Productivity", "score": 84},
    ]
    return jsonify({"ok": True, "items": items, "ts": _now().isoformat() + "Z"})


@app.post("/v1/build-pack")
def build_pack():
    ip = _client_ip()
    ok, retry = _rate_limit_ok(ip)
    if not ok:
        return jsonify({"error": "rate_limited", "retry_after": retry}), 429

    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode") or "niche").strip()

    # Accept multiple keys for input
    input_value = str(
        data.get("input")
        or data.get("niche")
        or data.get("topic")
        or data.get("value")
        or ""
    ).strip()

    if not input_value:
        return jsonify({"error": "bad_request", "message": "Missing input/niche"}), 400

    language = str(data.get("language") or data.get("lang") or "ar").strip()
    tone = str(data.get("tone") or "Authority").strip()
    platforms = data.get("platforms") or ["TikTok", "X", "LinkedIn"]
    if isinstance(platforms, str):
        platforms = [p.strip() for p in platforms.split(",") if p.strip()]
    elif not isinstance(platforms, list):
        platforms = ["TikTok", "X", "LinkedIn"]

    sync = bool(data.get("sync") or False)

    db = SessionLocal()
    try:
        # Backlog guard (reject only if queue is truly huge)
        backlog_cap = int(getattr(settings, "MAX_QUEUE_BACKLOG", 30) or 30)
        queued = db.query(Job).filter(Job.status == "queued").count()
        if queued >= backlog_cap:
            return jsonify({"error": "busy", "queued": queued, "backlog_cap": backlog_cap}), 429

        payload = {
            "mode": mode,
            "input": input_value,
            "language": language,
            "tone": tone,
            "platforms": platforms,
        }

        job = Job(status="queued", progress=0.0, request=payload)
        db.add(job)
        db.commit()

        job_id = job.id

    finally:
        db.close()

    if sync:
        # Process immediately (debug / demo)
        result = process_build_pack(job_id)
        # Return pack if done
        db2 = SessionLocal()
        try:
            j = db2.get(Job, job_id)
            p = db2.get(Pack, j.pack_id) if (j and j.pack_id) else None
            return jsonify({
                "ok": True,
                "job": {
                    "id": j.id if j else job_id,
                    "status": j.status if j else "unknown",
                    "progress": float(j.progress or 0.0) if j else 0.0,
                    "pack_id": j.pack_id if j else None,
                    "error_message": j.error_message if j else None,
                },
                "pack": p_to_dict(p) if p else None,
                "result": result,
            })
        finally:
            db2.close()

    # Async path: kick scheduler (NEVER reject as busy)
    _kick_scheduler(max_to_start=2)
    return jsonify({"ok": True, "job_id": job_id, "status": "queued", "ts": _now().isoformat() + "Z"}), 202


@app.get("/v1/jobs/<job_id>")
def job_status(job_id: str):
    # Opportunistically start more jobs while UI is polling
    _kick_scheduler(max_to_start=1)

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return jsonify({"error": "not_found"}), 404

        return jsonify({
            "ok": True,
            "job": {
                "id": job.id,
                "status": job.status,
                "progress": float(job.progress or 0.0),
                "pack_id": job.pack_id,
                "error_message": job.error_message,
                "error_trace": job.error_trace,
            },
            "ts": _now().isoformat() + "Z",
        })
    finally:
        db.close()


def p_to_dict(p: Optional[Pack]) -> Optional[Dict[str, Any]]:
    if not p:
        return None
    return {
        "id": p.id,
        "mode": p.mode,
        "input_value": p.input_value,
        "language": p.language,
        "platforms": p.platforms,
        "tone": p.tone,
        "genes": p.genes,
        "assets": p.assets,
        "visual": p.visual,
        "dominance": p.dominance,
        "sources": p.sources,
        "created_at": p.created_at.isoformat() + "Z" if p.created_at else None,
    }


@app.get("/v1/packs/<pack_id>")
def get_pack(pack_id: str):
    db = SessionLocal()
    try:
        p = db.get(Pack, pack_id)
        if not p:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"ok": True, "pack": p_to_dict(p), "ts": _now().isoformat() + "Z"})
    finally:
        db.close()


@app.post("/internal/worker-tick")
def internal_worker_tick():
    token = request.headers.get("X-Worker-Token", "")
    if not settings.WORKER_TICK_TOKEN or token != settings.WORKER_TICK_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    limit = int(request.args.get("limit", "1") or "1")
    out = worker_tick(limit=limit)
    return jsonify(out)


@app.post("/internal/admin/cleanup")
def admin_cleanup():
    token = request.headers.get("X-Worker-Token", "")
    if not settings.WORKER_TICK_TOKEN or token != settings.WORKER_TICK_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    db = SessionLocal()
    try:
        cleaned = _cleanup_stale_running(db)
        db.commit()
        running = _count_status(db, "running")
        queued = _count_status(db, "queued")
        return jsonify({"ok": True, "cleaned": cleaned, "running": running, "queued": queued, "ts": _now().isoformat() + "Z"})
    finally:
        db.close()
