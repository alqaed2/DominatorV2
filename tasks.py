# tasks.py
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select

from db import SessionLocal
from models import Job, Pack


def _now() -> datetime:
    return datetime.utcnow()


def _safe_text(x: Any) -> str:
    try:
        return str(x or "").strip()
    except Exception:
        return ""


def _json_blob(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return _safe_text(obj)


def _niche_lock_ok(mode: str, input_value: str, result: Dict[str, Any]) -> bool:
    """
    Hard guard: ensures output reflects user input.
    - url mode: require non-empty assets+genes
    - niche mode: niche phrase OR >=2 keywords must appear in output
    """
    mode = (mode or "niche").lower().strip()
    input_value = _safe_text(input_value)

    assets = (result or {}).get("assets") or {}
    genes = (result or {}).get("genes") or {}

    if mode == "url":
        return bool(assets) and bool(genes)

    if not input_value:
        return False

    blob = (_json_blob(result)).lower()
    if input_value.lower() in blob:
        return True

    toks: List[str] = []
    for w in input_value.replace("#", " ").split():
        w2 = "".join(ch for ch in w if ch.isalnum() or ch in "_-")
        w2 = w2.strip().lower()
        if len(w2) >= 3:
            toks.append(w2)

    toks = list(dict.fromkeys(toks))
    if len(toks) >= 2:
        hits = sum(1 for t in toks[:6] if t and t in blob)
        return hits >= 2

    return False


def _build_pack_payload(request_payload: Dict[str, Any]) -> Dict[str, Any]:
    # pipeline.py already contains Gemini + fallback logic (very good)
    from pipeline import run_build_pack
    return run_build_pack(request_payload)


def process_build_pack(job_id: str) -> Dict[str, Any]:
    """
    Process a single job with FULL SAFETY:
    - never leaves the job stuck due to exceptions
    - writes error_message + error_trace
    - creates Pack and attaches pack_id
    """
    job_id = _safe_text(job_id)
    if not job_id:
        raise RuntimeError("job_id is empty")

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise RuntimeError(f"Job not found: {job_id}")

        if job.status in ("done", "failed"):
            return {
                "ok": True,
                "job_id": job.id,
                "status": job.status,
                "pack_id": job.pack_id,
                "ts": _now().isoformat() + "Z",
            }

        job.status = "running"
        job.started_at = job.started_at or _now()
        if float(job.progress or 0.0) < 0.05:
            job.progress = 0.05
        db.commit()

        req = job.request or {}
        mode = _safe_text(req.get("mode") or "niche").lower()
        input_value = _safe_text(
            req.get("niche") or req.get("input") or req.get("topic") or req.get("url") or req.get("value")
        )

        t0 = time.time()
        job.progress = 0.15
        db.commit()

        result = _build_pack_payload(req)

        job.progress = 0.75
        db.commit()

        if not _niche_lock_ok(mode, input_value, result):
            raise RuntimeError("Niche-Lock failed: output does not reflect input")

        pack = Pack(
            mode=_safe_text(result.get("mode") or mode or "niche"),
            input_value=_safe_text(result.get("input_value") or input_value),
            language=_safe_text(result.get("language") or req.get("language") or req.get("lang") or "ar"),
            platforms=result.get("platforms") or req.get("platforms") or ["linkedin", "x", "tiktok"],
            tone=_safe_text(result.get("tone") or req.get("tone") or "authority"),
            genes=result.get("genes") or {},
            assets=result.get("assets") or {},
            visual=result.get("visual") or {},
            dominance=result.get("dominance") or {},
            sources=result.get("sources") or {},
        )
        db.add(pack)
        db.commit()
        db.refresh(pack)

        job.pack_id = pack.id
        job.status = "done"
        job.finished_at = _now()
        job.updated_at = _now()
        job.progress = 1.0
        job.error_message = None
        job.error_trace = None
        db.commit()

        took_ms = int((time.time() - t0) * 1000)
        return {
            "ok": True,
            "job_id": job.id,
            "pack_id": pack.id,
            "status": "done",
            "took_ms": took_ms,
            "ts": _now().isoformat() + "Z",
        }

    except Exception as e:
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.finished_at = _now()
                job.updated_at = _now()
                job.progress = float(job.progress or 0.0)
                job.error_message = str(e)
                job.error_trace = traceback.format_exc(limit=35)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


def worker_tick(limit: int = 1) -> Dict[str, Any]:
    """Process up to N queued jobs (safe for GitHub Actions tick)."""
    limit = max(1, int(limit or 1))
    started = time.time()
    processed: List[Dict[str, Any]] = []

    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(Job).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(limit)
            )
            .scalars()
            .all()
        )

        for j in rows:
            jid = str(j.id)
            updated = (
                db.query(Job)
                .filter(Job.id == jid, Job.status == "queued")
                .update(
                    {Job.status: "running", Job.started_at: _now(), Job.progress: 0.05},
                    synchronize_session=False,
                )
            )
            db.commit()
            if not updated:
                continue

            try:
                processed.append(process_build_pack(jid))
            except Exception as e:
                processed.append({"ok": False, "job_id": jid, "error": str(e)})

        return {
            "ok": True,
            "limit": limit,
            "processed": processed,
            "took_ms": int((time.time() - started) * 1000),
            "ts": _now().isoformat() + "Z",
        }
    finally:
        db.close()
