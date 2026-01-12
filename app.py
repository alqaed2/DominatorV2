from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime

from flask import Flask, jsonify, request, render_template
from jinja2 import TemplateNotFound
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from config import settings
from db import init_db, SessionLocal
from models import Job, Pack
from queue import get_queue
from tasks import process_build_pack
from services.trends import get_trending_hashtags


app = Flask(__name__, static_folder="static", template_folder="templates")


# --- In-memory rate limiter (upgrade later to Redis-based) ---
_requests_by_ip: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit_ok(ip: str) -> bool:
    limit = settings.MAX_REQUESTS_PER_IP_PER_MIN
    if limit <= 0:
        return True
    now = time.time()
    window = 60.0
    q = _requests_by_ip[ip]
    while q and (now - q[0]) > window:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def _db() -> Session:
    return SessionLocal()


def _count_by_status(db: Session, status: str) -> int:
    stmt = select(Job).where(Job.status == status)
    return len(list(db.execute(stmt).scalars().all()))


def _job_to_dict(job: Job) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress or 0.0,
        "pack_id": job.pack_id,
        "error": job.error_message,
    }


def _pack_to_dict(pack: Pack, job_id: str | None = None) -> dict:
    return {
        "pack_id": pack.id,
        "job_id": job_id,
        "mode": pack.mode,
        "input_value": pack.input_value,
        "language": pack.language,
        "platforms": pack.platforms or [],
        "tone": pack.tone,
        "genes": pack.genes or {},
        "assets": pack.assets or {},
        "visual": pack.visual or {},
        "dominance": pack.dominance or {},
        "sources": pack.sources or {},
        "created_at": pack.created_at.isoformat() if pack.created_at else None,
    }


@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Worker-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "AI-DOMINATOR", "ts": datetime.utcnow().isoformat()})


@app.get("/readyz")
def readyz():
    try:
        db = _db()
        db.execute(select(1))
        db.close()
        return jsonify({"ready": True})
    except Exception as e:
        return jsonify({"ready": False, "error": str(e)}), 503


@app.get("/")
def index():
    try:
        return render_template("index.html")
    except TemplateNotFound:
        return (
            "<h2>AI DOMINATOR API Online</h2>"
            "<p>Use POST /v1/build-pack and GET /v1/jobs/&lt;job_id&gt;</p>",
            200,
        )


@app.get("/v1/trending-hashtags")
def trending_hashtags():
    tags = get_trending_hashtags(limit=15)
    return jsonify({"hashtags": tags})


@app.post("/v1/build-pack")
def build_pack():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    ip = ip.split(",")[0].strip()

    if not _rate_limit_ok(ip):
        return jsonify({"error": "rate_limited"}), 429

    payload = request.get_json(silent=True) or {}
    mode = (payload.get("mode") or "niche").lower().strip()

    # Normalize inputs
    if mode == "url":
        input_value = (payload.get("url") or "").strip()
        if not input_value:
            return jsonify({"error": "missing_url"}), 400
        payload["url"] = input_value
        payload["mode"] = "url"
    else:
        payload["mode"] = "niche"
        input_value = (payload.get("niche") or "").strip()
        if not input_value:
            return jsonify({"error": "missing_niche"}), 400
        payload["niche"] = input_value

    payload.setdefault("platforms", ["linkedin", "x", "tiktok"])
    payload.setdefault("language", "ar")
    payload.setdefault("tone", "authority")
    payload.setdefault("include_visual", True)

    force_sync = bool(payload.get("sync", False))
    async_enabled = bool(settings.ASYNC_ENABLED) and not force_sync

    db = _db()
    try:
        running = _count_by_status(db, "running")
        queued = _count_by_status(db, "queued")

        if running >= settings.MAX_CONCURRENT_JOBS:
            return jsonify({"error": "busy", "running": running}), 429

        if queued >= settings.MAX_QUEUE_BACKLOG:
            return jsonify({"error": "queue_backlog_full", "queued": queued}), 429

        job = Job(status="queued", progress=0.0, request=payload)
        db.add(job)
        db.commit()
        db.refresh(job)

        q = get_queue()

        # Case A: Full async (Redis + Paid Worker exists)
        if async_enabled and q is not None:
            q.enqueue("tasks.process_build_pack", job.id)
            return jsonify(_job_to_dict(job)), 202

        # Case B: Free mode async (no worker) -> leave queued, process via /internal/worker-tick
        if async_enabled and q is None and settings.WORKER_TICK_TOKEN:
            return jsonify(_job_to_dict(job)), 202

        # Case C: fallback sync (for local/dev or if no token)
        pack_id = process_build_pack(job.id)
        job = db.get(Job, job.id)
        if not job:
            return jsonify({"error": "job_lost"}), 500

        if job.status == "done" and job.pack_id:
            pack = db.get(Pack, job.pack_id)
            return jsonify({"job": _job_to_dict(job), "pack": _pack_to_dict(pack, job_id=job.id)}), 200

        return jsonify(_job_to_dict(job)), 500

    finally:
        db.close()


@app.get("/v1/jobs/<job_id>")
def job_status(job_id: str):
    db = _db()
    try:
        job = db.get(Job, job_id)
        if not job:
            return jsonify({"error": "not_found"}), 404
        return jsonify(_job_to_dict(job)), 200
    finally:
        db.close()


@app.get("/v1/packs/<pack_id>")
def get_pack(pack_id: str):
    db = _db()
    try:
        pack = db.get(Pack, pack_id)
        if not pack:
            return jsonify({"error": "not_found"}), 404
        return jsonify(_pack_to_dict(pack)), 200
    finally:
        db.close()


def _claim_next_job_postgres(db: Session) -> str | None:
    # Atomically claim a queued job (Postgres only)
    sql = text("""
    WITH next AS (
      SELECT id
      FROM jobs
      WHERE status = 'queued'
      ORDER BY created_at ASC
      LIMIT 1
      FOR UPDATE SKIP LOCKED
    )
    UPDATE jobs
    SET status = 'running',
        started_at = NOW(),
        updated_at = NOW(),
        progress = 0.01
    FROM next
    WHERE jobs.id = next.id
    RETURNING jobs.id;
    """)
    row = db.execute(sql).fetchone()
    return row[0] if row else None


def _claim_next_job_fallback(db: Session) -> str | None:
    # Fallback (SQLite): best-effort
    stmt = select(Job).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(1)
    job = db.execute(stmt).scalars().first()
    if not job:
        return None
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.updated_at = datetime.utcnow()
    job.progress = 0.01
    db.add(job)
    db.commit()
    return job.id


@app.post("/internal/worker-tick")
def worker_tick():
    # SECURITY: require token
    token = request.headers.get("X-Worker-Token") or request.args.get("token")
    if not settings.WORKER_TICK_TOKEN or token != settings.WORKER_TICK_TOKEN:
        return jsonify({"error": "forbidden"}), 403

    limit_raw = request.args.get("limit", "1")
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 1
    limit = max(1, min(3, limit))

    processed = []
    db = _db()
    try:
        for _ in range(limit):
            job_id = None
            # Try Postgres atomic claim first
            try:
                job_id = _claim_next_job_postgres(db)
            except Exception:
                job_id = _claim_next_job_fallback(db)

            if not job_id:
                break

            # Process job (this function manages its own DB session)
            process_build_pack(job_id)
            processed.append(job_id)

        return jsonify({"processed": processed, "count": len(processed)}), 200
    finally:
        db.close()


# --- Startup ---
try:
    init_db()
except Exception:
    pass
