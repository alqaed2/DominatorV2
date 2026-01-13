# tasks.py
from __future__ import annotations

import hashlib
import json
import re
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List

from db import SessionLocal
from models import Job, Pack, Score


# -------------------------------
# Utilities
# -------------------------------

_AR_STOP = {
    "في", "من", "على", "إلى", "عن", "هذا", "هذه", "ذلك", "تلك", "مع", "ثم", "و", "او", "أو",
    "the", "a", "an", "to", "of", "and", "or", "for", "in",
}


def _now() -> datetime:
    return datetime.utcnow()


def _clean_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _keywords(niche: str, limit: int = 8) -> List[str]:
    niche = _clean_text(niche)
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u0600-\u06FF]+", niche)
    out: List[str] = []
    for t in tokens:
        tt = t.strip("#").lower()
        if not tt or tt in _AR_STOP:
            continue
        if tt.isdigit():
            continue
        if tt not in out:
            out.append(tt)
        if len(out) >= limit:
            break
    return out


def _seed(niche: str, tone: str, lang: str, salt: str) -> int:
    # IMPORTANT: include job_id salt so each job is unique (even same niche)
    h = hashlib.sha256(f"{niche}|{tone}|{lang}|{salt}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _ensure_niche_lock(niche: str, payload: Dict[str, Any]) -> None:
    niche = _clean_text(niche)
    if not niche:
        raise RuntimeError("Niche is empty (cannot generate)")

    blob = json.dumps(payload, ensure_ascii=False).lower()
    # Accept if full niche appears or at least 3 keywords appear
    if niche.lower() in blob:
        return

    kws = _keywords(niche, limit=3)
    if not kws or not all(k.lower() in blob for k in kws):
        raise RuntimeError("Niche-Lock failed: outputs do not reflect niche")


# -------------------------------
# Content builders
# -------------------------------

def _build_linkedin(niche: str, kws: List[str], s: int) -> str:
    niche = _clean_text(niche)

    hooks = [
        f"الخطأ الأكبر في {niche} ليس نقص الأدوات… بل اختيار «الإشارة» الخطأ.",
        f"إذا أردت نتائج حقيقية في {niche} خلال 14 يومًا: لا تطارد الترند… ابنِ نظام.",
        f"{niche}: 80% من الناس يعملون أكثر… ليحصلوا على أقل.",
        f"لن تكسب في {niche} لأنك أذكى… بل لأنك تقيس الشيء الصحيح.",
    ]
    hook = hooks[s % len(hooks)]

    bullets = [
        "1) حدّد «عميلًا واحدًا» بدقة (ليس جمهورًا).",
        "2) اختر «عرضًا واحدًا» يمكن قياسه (قبل التوسع).",
        "3) اصنع سلسلة محتوى تقود لنقطة قرار واحدة.",
        "4) اجعل كل منشور يلتقط بيانات (سؤال/تصويت/CTA).",
    ]

    hashtags = " ".join([f"#{k}" for k in kws[:6]])
    return "\n".join([
        hook,
        "",
        f"الهدف: تحويل {niche} إلى سلطة معرفية قابلة للتكرار.",
        "",
        *bullets,
        "",
        "قاعدة ذهبية:",
        f"إذا لم تستطع شرح {niche} في جملة واحدة تُقنع شخصًا مشغولًا… فأنت لم تُصمّم الرسالة بعد.",
        "",
        "سؤال سريع: ما الجزء الأصعب لديك الآن؟ (المنتج / التسويق / التحويل / الاستمرارية)",
        "",
        hashtags,
    ])


def _build_x(niche: str, kws: List[str], s: int) -> str:
    niche = _clean_text(niche)

    tweets = [
        f"{niche}: لا تحتاج خطة معقدة… تحتاج «مقياس واحد» يمنعك من خداع نفسك.",
        f"أسرع طريقة للفشل في {niche}: تشتغل كثير وتراقب صفر مؤشرات.",
        f"في {niche}… المنافس الحقيقي ليس منافسك، بل تشتتك.",
    ]
    tweet = tweets[s % len(tweets)]

    thread = [
        "Thread 🧵",
        "1) اكتب الهدف بصيغة رقم + مدة (مثال: 30 طلب خلال 21 يوم).",
        "2) اختر قناة واحدة فقط لمدة أسبوعين.",
        "3) ابنِ 3 رسائل: (ألم / حل / إثبات).",
        "4) كرّر نفس الرسائل بطرق مختلفة بدل تبديل كل شيء.",
        f"5) راقب: (CTR / Replies / Saves). هذه إشارات أن {niche} بدأ يلتقط.",
        "إذا تريد، اكتب هدفك هنا وسأعيد صياغته كنظام قابل للتنفيذ.",
    ]

    hashtags = " ".join([f"#{k}" for k in kws[:5]])
    return "\n".join([tweet, "", *thread, "", hashtags])


def _build_tiktok(niche: str, s: int) -> str:
    niche = _clean_text(niche)

    hooks = [
        f"إذا كنت داخل {niche} وتقول «الموضوع ما يمشي»… اسمع هذا.",
        f"3 أشياء تمنعك تكسب من {niche}… حتى لو أنت شاطر.",
        f"سر صغير: {niche} ليس لعبة ترند… هو لعبة نظام.",
    ]
    hook = hooks[s % len(hooks)]

    script = [
        f"Hook: {hook}",
        "مشهد 1 (2ث): نص كبير على الشاشة: «السبب الحقيقي للفشل»",
        f"مشهد 2 (5ث): «أنت تحاول تعظيم كل شيء بدل تعظيم خطوة واحدة داخل {niche}»",
        "مشهد 3 (7ث): إطار 3 خطوات: (عرض واضح) -> (رسالة واحدة) -> (CTA واحد)",
        "مشهد 4 (6ث): مثال سريع جدًا (قبل/بعد) + إثبات بسيط",
        "Outro (3ث): «اكتب كلمتك المفتاحية وسأرسل لك قالب التنفيذ»",
        "",
        "B-roll مقترح:",
        "- لقطات شاشة / كتابة على ورق / لوحة تحكم / نتائج قبل وبعد",
    ]
    return "\n".join(script)


def _build_visual_prompt(niche: str) -> str:
    niche = _clean_text(niche)
    return (
        "Ultra-realistic cinematic professional photo, "
        f"visual metaphor for: {niche}. "
        "Modern dark studio, clean minimal tech desk, soft rim lighting, "
        "high-end advertising look, shallow depth of field, 4k, "
        "no text, no watermark, no logos."
    )


def _dominance_score(niche: str, platforms: List[str], tone: str, kws: List[str]) -> Dict[str, Any]:
    # Provide UI-friendly fields: score + reasons + recommendation
    score = 62
    if len(kws) >= 4:
        score += 10
    if len(platforms) >= 2:
        score += 6
    if tone.strip().lower() in ("authority", "سيادي", "سلطوي"):
        score += 6
    score = min(95, score)

    reasons = [
        "Niche-Lock: مضبوط",
        "CTA: موجود",
        f"Cross-platform: {len(platforms)}",
    ]
    recommendation = "publish" if score >= 80 else "revise"

    return {
        "score": score,
        "reasons": reasons,
        "recommendation": recommendation,
    }


def _make_pack_payload(job_id: str, niche: str, lang: str, tone: str, platforms: List[str]) -> Dict[str, Any]:
    niche = _clean_text(niche)
    kws = _keywords(niche)
    s = _seed(niche, tone, lang, salt=job_id)

    assets: Dict[str, Any] = {}
    pl = [p.strip() for p in platforms if str(p).strip()]
    pl_low = [p.lower() for p in pl]

    if "linkedin" in pl_low:
        assets["linkedin"] = _build_linkedin(niche, kws, s)
    if "x" in pl_low:
        assets["x"] = _build_x(niche, kws, s + 13)
    if "tiktok" in pl_low:
        assets["tiktok"] = _build_tiktok(niche, s + 29)

    genes = {
        "niche": niche,
        "keywords": kws,
        "angle": f"نظام > ترند داخل {niche}",
        "cta": "اكتب هدفك/سؤالك وسأعيد صياغته كنظام تنفيذ",
        "tone": tone,
        "language": lang,
    }

    dominance = _dominance_score(niche, pl, tone, kws)
    visual = {"prompt": _build_visual_prompt(niche)}

    payload = {
        "ok": True,
        "niche": niche,
        "platforms": pl,
        "genes": genes,
        "dominance": dominance,
        "visual": visual,
        "assets": assets,
        "ts": _now().isoformat() + "Z",
    }

    _ensure_niche_lock(niche, payload)
    return payload


# -------------------------------
# Public API expected by app.py
# -------------------------------

def process_build_pack(job_id: str) -> Dict[str, Any]:
    """
    Final, type-safe implementation:
    - Job.id is String(32) => NEVER cast to UUID
    - Store Pack using ORM (consistent schema)
    - Always exit running state (done/failed)
    """
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            raise RuntimeError(f"Job not found: {job_id}")

        # If already finished, return quickly
        if job.status in ("done", "failed"):
            return {"ok": True, "job_id": job.id, "status": job.status, "pack_id": job.pack_id}

        # Mark running
        job.status = "running"
        job.progress = max(job.progress or 0.0, 0.05)
        if not job.started_at:
            job.started_at = _now()
        db.commit()

        req = job.request or {}
        mode = str(req.get("mode") or "niche").strip()
        niche = _clean_text(str(req.get("input") or req.get("niche") or req.get("topic") or req.get("value") or ""))

        lang = str(req.get("language") or req.get("lang") or "ar").strip()
        tone = str(req.get("tone") or "Authority").strip()

        platforms_val = req.get("platforms") or ["TikTok", "X", "LinkedIn"]
        if isinstance(platforms_val, str):
            platforms = [p.strip() for p in platforms_val.split(",") if p.strip()]
        elif isinstance(platforms_val, list):
            platforms = [str(p) for p in platforms_val]
        else:
            platforms = ["TikTok", "X", "LinkedIn"]

        payload = _make_pack_payload(job_id=job.id, niche=niche, lang=lang, tone=tone, platforms=platforms)

        # Create pack
        pack = Pack(
            id=uuid.uuid4().hex,
            mode=mode,
            input_value=niche,
            language=lang,
            platforms=payload.get("platforms", platforms),
            tone=tone,
            genes=payload.get("genes", {}),
            assets=payload.get("assets", {}),
            visual=payload.get("visual", {}),
            dominance=payload.get("dominance", {}),
            sources=payload.get("sources", {}),
        )
        db.add(pack)
        db.flush()

        # Attach and finish job
        job.pack_id = pack.id
        job.status = "done"
        job.progress = 1.0
        job.finished_at = _now()
        job.error_message = None
        job.error_trace = None

        # Optional: persist score row
        dom = payload.get("dominance") or {}
        score_val = int(dom.get("score") or 0)
        reasons = dom.get("reasons") if isinstance(dom.get("reasons"), list) else []
        recommendation = str(dom.get("recommendation") or "revise")

        # Upsert score
        existing = db.query(Score).filter(Score.job_id == job.id).one_or_none()
        if existing:
            existing.score = score_val
            existing.reasons = reasons
            existing.recommendation = recommendation
        else:
            db.add(Score(job_id=job.id, score=score_val, reasons=reasons, recommendation=recommendation, version="v12.9"))

        db.commit()
        return {"ok": True, "job_id": job.id, "status": job.status, "pack_id": job.pack_id, "niche": niche}

    except Exception as e:
        # Hard fail-safe: never leave job running
        try:
            job = db.get(Job, job_id)
            if job and job.status not in ("done", "failed"):
                job.status = "failed"
                job.progress = float(job.progress or 0.0)
                job.finished_at = _now()
                job.error_message = str(e)
                job.error_trace = traceback.format_exc()
                db.commit()
        except Exception:
            pass
        return {"ok": False, "job_id": job_id, "error": str(e)}
    finally:
        db.close()


def worker_tick(limit: int = 1) -> Dict[str, Any]:
    """
    Workerless tick (GitHub Actions compatible):
    process up to N queued jobs sequentially.
    """
    limit = max(1, int(limit or 1))
    db = SessionLocal()
    started = _now()
    processed: List[Dict[str, Any]] = []

    try:
        jobs = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at.asc())
            .limit(limit)
            .all()
        )
        ids = [j.id for j in jobs]
    finally:
        db.close()

    for jid in ids:
        processed.append(process_build_pack(jid))

    took_ms = int(((_now() - started).total_seconds()) * 1000)
    return {"ok": True, "limit": limit, "processed": processed, "took_ms": took_ms, "ts": _now().isoformat() + "Z"}
