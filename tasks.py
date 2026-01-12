from __future__ import annotations

import traceback
from datetime import datetime

from sqlalchemy.orm import Session

from db import SessionLocal
from models import Job, Pack, Event, Score
from pipeline import run_build_pack


def emit_event(db: Session, job_id: str, event_type: str, payload: dict | None = None):
    ev = Event(job_id=job_id, type=event_type, payload=payload or {})
    db.add(ev)
    db.commit()


def update_job(db: Session, job: Job, **kwargs):
    for k, v in kwargs.items():
        setattr(job, k, v)
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)


def process_build_pack(job_id: str) -> str:
    """
    Worker entrypoint.
    Returns pack_id on success.
    """
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return ""

        update_job(db, job, status="running", started_at=datetime.utcnow(), progress=0.05)
        emit_event(db, job_id, "IngestRequested", {"request": job.request})

        # Core pipeline
        result = run_build_pack(job.request)

        emit_event(db, job_id, "GenesExtracted", {"ok": True})
        update_job(db, job, progress=0.55)

        # Save pack
        pack = Pack(
            mode=result["mode"],
            input_value=result["input_value"],
            language=result["language"],
            platforms=result["platforms"],
            tone=result["tone"],
            genes=result["genes"],
            assets=result["assets"],
            visual=result["visual"],
            dominance=result["dominance"],
            sources=result["sources"],
        )
        db.add(pack)
        db.commit()
        db.refresh(pack)

        emit_event(db, job_id, "PackReady", {"pack_id": pack.id})
        update_job(db, job, status="done", finished_at=datetime.utcnow(), progress=1.0, pack_id=pack.id)

        # Save score row (normalized)
        dom = result.get("dominance") or {}
        score = Score(
            job_id=job_id,
            score=int(dom.get("score") or 0),
            reasons=list(dom.get("reasons") or []),
            recommendation=str(dom.get("recommendation") or "revise"),
            version="v1",
        )
        db.add(score)
        db.commit()

        return pack.id

    except Exception as e:
        tb = traceback.format_exc()
        try:
            job = db.get(Job, job_id)
            if job:
                update_job(db, job, status="failed", finished_at=datetime.utcnow(), error_message=str(e), error_trace=tb)
                emit_event(db, job_id, "PackFailed", {"error": str(e)})
        except Exception:
            pass
        return ""
    finally:
        db.close()
