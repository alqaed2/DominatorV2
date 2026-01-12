from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from datetime import datetime

from flask import Flask, jsonify, request, render_template
from jinja2 import TemplateNotFound
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session
from werkzeug.exceptions import HTTPException

from config import settings
from db import init_db, SessionLocal
from models import Job, Pack
from rq_queue import get_queue
from tasks import process_build_pack
from services.trends import get_trending_hashtags


app = Flask(__name__, static_folder="static", template_folder="templates")

_requests_by_ip: dict[str, deque[float]] = defaultdict(deque)

_DB_INIT_DONE = False
_DB_INIT_ERR: str | None = None

_BG_LOCK = threading.Lock()
_BG_ACTIVE: set[str] = set()


def ensure_db():
    global _DB_INIT_DONE, _DB_INIT_ERR
    if _DB_INIT_DONE:
        return
    try:
        init_db()
        _DB_INIT_DONE = True
        _DB_INIT_ERR = None
    except Exception as e:
        _DB_INIT_DONE = False
        _DB_INIT_ERR = str(e)
        raise


def _db() -> Session:
    return SessionLocal()


def _rate_limit_ok(ip: str) -> bool:
    limit = getattr(settings, "MAX_REQUESTS_PER_IP_PER_MIN", 60)
    if not limit or limit <= 0:
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


def _count_status(db: Session, status: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Job).where(Job.status == status)) or 0)


def _job_to_dict(job: Job) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": float(job.progress or 0.0),
        "pack_id": job.pack_id,
        "error": getattr(job, "error_message", None),
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


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    return jsonify({"error": "internal_server_error", "detail": str(e)}), 500


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
        try:
            ensure_db()
        except Exception:
            pass
        return jsonify({"ready": True, "db_init": _DB_INIT_DONE, "db_init_err": _DB_INIT_ERR})
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
    ensure_db()
    tags = get_trending_hashtags(limit=15)
    return jsonify({"hashtags": tags})


def _kick_background(job_id: str) -> bool:
    with _BG_LOCK:
        if job_id in _BG_ACTIVE:
            return False
        _BG_ACTIVE.add(job_id)

    def _runner():
        try:
            process_build_pack(job_id)
        finally:
            with _BG_LOCK:
                _BG_ACTIVE.discard(job_id)

    t = threading.Thread(target=_runner, name=f"job-{job_id}", daemon=True)
    t.start()
    return True


def _atomic_set_running(db: Session, job_id: str) -> bool:
    """
    DB-safe atomic transition:
    queued -> running
    (لا يعتمد على أسماء جداول نصية، يستخدم ORM مباشرة)
    """
    now = datetime.utcnow()
    stmt = (
        update(Job)
        .where(Job.id == job_id, Job.status == "queued")
        .values(status="running", started_at=now, updated_at=now, progress=0.01)
    )
    res = db.execute(stmt)
    db.commit()
    return (res.rowcount or 0) == 1


def _atomic_claim_oldest_queued(db: Session) -> str | None:
    """
    Claim أقدم queued job بشكل متوافق (بدون SQL نصّي).
    """
    job_id = db.scalar(select(Job.id).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(1))
    if not job_id:
        return None
    ok = _atomic_set_running(db, job_id)
    return job_id if ok else None


@app.post("/v1/build-pack")
def build_pack():
    ensure_db()

    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    ip = ip.split(",")[0].strip()

    if not _rate_limit_ok(ip):
        return jsonify({"error": "rate_limited"}), 429

    payload = request.get_json(silent=True) or {}
    mode = (payload.get("mode") or "niche").lower().strip()

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
    async_enabled = bool(getattr(settings, "ASYNC_ENABLED", True)) and not force_sync

    db = _db()
    try:
        running = _count_status(db, "running")
        queued = _count_status(db, "queued")

        if running >= getattr(settings, "MAX_CONCURRENT_JOBS", 2):
            return jsonify({"error": "busy", "running": running}), 429

        if queued >= getattr(settings, "MAX_QUEUE_BACKLOG", 50):
            return jsonify({"error": "queue_backlog_full", "queued": queued}), 429

        job = Job(status="queued", progress=0.0, request=payload)
        db.add(job)
        db.commit()
        db.refresh(job)

        # ملاحظة: لا نستخدم RQ إلا لو فعّلت USE_RQ صراحة
        use_rq = bool(getattr(settings, "USE_RQ", False))
        q = get_queue() if use_rq else None

        if async_enabled and q is not None:
            q.enqueue("tasks.process_build_pack", job.id)
            return jsonify(_job_to_dict(job)), 202

        if async_enabled:
            # FREE/AUTOPILOT: شغّل فورًا من نفس السيرفر
            if not getattr(settings, "WORKER_TICK_TOKEN", None):
                return jsonify({"error": "missing_WORKER_TICK_TOKEN_on_server"}), 503

            if _atomic_set_running(db, job.id):
                _kick_background(job.id)

            # أعد قراءة job بحالة محدثة
            job2 = db.get(Job, job.id)
            return jsonify(_job_to_dict(job2 or job)), 202

        # fallback sync (يفضل عدم استخدامه على Render)
        process_build_pack(job.id)
        job2 = db.get(Job, job.id)
        if not job2:
            return jsonify({"error": "job_lost"}), 500
        if job2.status == "done" and job2.pack_id:
            pack = db.get(Pack, job2.pack_id)
            return jsonify({"job": _job_to_dict(job2), "pack": _pack_to_dict(pack, job_id=job2.id)}), 200
        return jsonify(_job_to_dict(job2)), 500

    finally:
        db.close()


@app.get("/v1/jobs/<job_id>")
def job_status(job_id: str):
    ensure_db()
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
    ensure_db()
    db = _db()
    try:
        pack = db.get(Pack, pack_id)
        if not pack:
            return jsonify({"error": "not_found"}), 404
        return jsonify(_pack_to_dict(pack)), 200
    finally:
        db.close()


@app.post("/internal/worker-tick")
def worker_tick():
    """
    Failsafe tick:
    يلتقط أقدم queued job ويطلقه (غير معتمد عليه كمسار رئيسي).
    """
    ensure_db()

    token = request.headers.get("X-Worker-Token") or request.args.get("token")
    if not getattr(settings, "WORKER_TICK_TOKEN", None) or token != settings.WORKER_TICK_TOKEN:
        return jsonify({"error": "forbidden"}), 403

    try:
        limit = int(request.args.get("limit", "1"))
    except Exception:
        limit = 1
    limit = max(1, min(3, limit))

    kicked = []
    db = _db()
    try:
        for _ in range(limit):
            jid = _atomic_claim_oldest_queued(db)
            if not jid:
                break
            _kick_background(jid)
            kicked.append(jid)
        return jsonify({"kicked": kicked, "count": len(kicked)}), 200
    finally:
        db.close()


try:
    ensure_db()
except Exception:
    pass
