# tasks.py
from __future__ import annotations

import json
import re
import traceback
import uuid
from datetime import datetime

from db import SessionLocal
from models import Job, Pack


# -----------------------------
# Helpers
# -----------------------------

_AR_STOP = {
    "في", "من", "على", "إلى", "عن", "هذا", "هذه", "ذلك", "تلك", "مع", "ثم",
    "و", "او", "أو",
    "the", "a", "an", "to", "of", "and", "or", "for", "in"
}


def _now():
    return datetime.utcnow()


def _clean(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _safe_json(x):
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return {"raw": x}
    return {"raw": str(x)}


def _keywords(niche: str, limit: int = 6):
    niche = _clean(niche)
    toks = re.findall(r"[A-Za-z0-9_]+|[\u0600-\u06FF]+", niche)
    out = []
    for t in toks:
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


def _seed_int(niche: str, tone: str, lang: str) -> int:
    base = f"{niche}|{tone}|{lang}".encode("utf-8")
    h = 0
    for b in base:
        h = (h * 131 + b) & 0xFFFFFFFF
    return int(h)


def _build_linkedin(niche: str, tone: str, lang: str, seed: int) -> str:
    niche = _clean(niche)
    hooks = [
        f"الناس تفشل في {niche} لسبب واحد: يقيسون الضجيج بدل الإشارة.",
        f"إذا أردت نتائج حقيقية في {niche} خلال 14 يومًا… ابنِ نظامًا لا منشورًا.",
        f"{niche}: 80% يعملون أكثر… ليحصلوا على أقل. إليك لماذا.",
        f"لن تربح في {niche} لأنك أذكى… بل لأنك تختار المعيار الصحيح.",
    ]
    hook = hooks[seed % len(hooks)]
    kws = _keywords(niche)
    hashtags = " ".join([f"#{k}" for k in kws[:5]])

    bullets = [
        "1) حدّد «عميلًا واحدًا» بدقة (ليس جمهورًا عامًا).",
        "2) اختر «عرضًا واحدًا» يمكن قياسه (قبل التوسع).",
        "3) اكتب 3 رسائل ثابتة: (ألم / حل / إثبات).",
        "4) اجعل كل منشور يلتقط بيانات (سؤال / تصويت / CTA).",
    ]

    return "\n".join([
        hook,
        "",
        f"هدفنا: تحويل {niche} إلى سلطة معرفية قابلة للتكرار.",
        "",
        *bullets,
        "",
        f"قاعدة ذهبية: إذا لم تستطع شرح {niche} في جملة واحدة تقنع شخصًا مشغولًا… فأنت لم تُصمّم الرسالة بعد.",
        "",
        "سؤال سريع: ما أصعب جزء لديك الآن؟ (المنتج / التسويق / التحويل / الاستمرارية)",
        "",
        hashtags,
    ])


def _build_x(niche: str, tone: str, lang: str, seed: int) -> str:
    niche = _clean(niche)
    tweets = [
        f"{niche}: لا تحتاج خطة معقدة… تحتاج «مقياس واحد» يمنعك من خداع نفسك.",
        f"أسرع طريق للفشل في {niche}: تشتغل كثير وتراقب صفر مؤشرات.",
        f"في {niche}… المنافس الحقيقي ليس منافسك، بل تشتتك.",
    ]
    tweet = tweets[seed % len(tweets)]
    kws = _keywords(niche)
    hashtags = " ".join([f"#{k}" for k in kws[:4]])

    thread = [
        "Thread 🧵",
        "1) اكتب هدفك بصيغة (رقم + مدة).",
        "2) اختر قناة واحدة فقط لمدة أسبوعين.",
        "3) ابنِ 3 رسائل ثابتة (ألم/حل/إثبات).",
        "4) كرّر الرسائل بأمثلة مختلفة بدل تبديل كل شيء.",
        f"5) راقب: Replies / Saves / CTR — هذه إشارات أن {niche} بدأ يلتقط.",
        "اكتب هدفك هنا وسأعيد صياغته كنظام تنفيذ.",
    ]
    return "\n".join([tweet, "", *thread, "", hashtags])


def _build_tiktok(niche: str, tone: str, lang: str, seed: int) -> str:
    niche = _clean(niche)
    hooks = [
        f"إذا كنت داخل {niche} وتقول «ما يمشي»… اسمع هذا.",
        f"3 أشياء تمنعك تكسب من {niche}… حتى لو أنت شاطر.",
        f"سر صغير: {niche} ليس لعبة ترند… هو لعبة نظام.",
    ]
    hook = hooks[seed % len(hooks)]

    return "\n".join([
        f"Hook: {hook}",
        "مشهد 1 (2s): نص كبير: «السبب الحقيقي للفشل»",
        f"مشهد 2 (5s): «أنت تحاول تعظيم كل شيء بدل تعظيم خطوة واحدة داخل {niche}»",
        "مشهد 3 (7s): إطار 3 خطوات: (عرض واضح) -> (رسالة واحدة) -> (CTA واحد)",
        "مشهد 4 (6s): مثال سريع قبل/بعد + إثبات بسيط",
        "Outro (3s): «اكتب كلمتك المفتاحية وسأرسل لك قالب التنفيذ»",
    ])


def _visual_prompt(niche: str) -> str:
    niche = _clean(niche)
    return (
        "Ultra-realistic cinematic professional photo, "
        f"visual metaphor for: {niche}. "
        "Modern dark studio, clean minimal tech desk, soft rim lighting, "
        "high-end advertising look, shallow depth of field, 4k, "
        "no text, no watermark, no logos."
    )


def _dominance_score(niche: str, platforms: list[str], tone: str) -> dict:
    kws = _keywords(niche)
    s = 60
    if len(kws) >= 4:
        s += 10
    if any(p.lower() == "tiktok" for p in platforms):
        s += 5
    if tone.lower() in ["authority", "سلطوي", "سيادي"]:
        s += 5
    s = min(95, s)
    return {
        "score": s,
        "signals": [
            "Niche-Lock: ON",
            "CTA: ON",
            "Cross-platform: ON" if len(platforms) >= 2 else "Single-platform",
        ],
        "risk": "Low" if s >= 75 else "Medium",
    }


def _ensure_niche_lock(niche: str, assets: dict) -> None:
    niche = _clean(niche)
    blob = json.dumps(assets, ensure_ascii=False)
    if niche and niche not in blob:
        # Accept keyword coverage as fallback
        kws = _keywords(niche, limit=3)
        low = blob.lower()
        if not kws or not all(k.lower() in low for k in kws):
            raise RuntimeError("Niche-Lock failed: outputs do not reflect niche")


# -----------------------------
# Main worker function
# -----------------------------

def process_build_pack(job_id: str):
    """
    Generates a pack for the given job_id and updates DB:
      - Job.status -> done/failed
      - Job.pack_id set
      - Pack inserted with content that MUST differ with niche
    """
    db = SessionLocal()
    try:
        job = db.get(Job, str(job_id))  # ✅ job.id is VARCHAR in your DB
        if not job:
            raise RuntimeError(f"Job not found: {job_id}")

        req = _safe_json(getattr(job, "request", None))

        mode = (req.get("mode") or "niche").strip().lower()
        language = (req.get("language") or "ar").strip()
        tone = (req.get("tone") or "Authority").strip()

        platforms = req.get("platforms") or ["TikTok", "X", "LinkedIn"]
        if isinstance(platforms, str):
            platforms = [p.strip() for p in platforms.split(",") if p.strip()]
        platforms = [str(p) for p in platforms]

        if mode == "url":
            input_value = _clean(req.get("url", ""))
        else:
            input_value = _clean(req.get("niche", ""))

        if not input_value:
            raise RuntimeError("Missing niche/url in job.request")

        # Mark processing progress
        if hasattr(job, "progress"):
            job.progress = 0.15
        if hasattr(job, "updated_at"):
            job.updated_at = _now()
        if hasattr(job, "status"):
            job.status = "processing"
        db.commit()

        seed = _seed_int(input_value, tone, language)

        assets = {}
        pl = [p.lower() for p in platforms]
        if "linkedin" in pl:
            assets["linkedin"] = _build_linkedin(input_value, tone, language, seed)
        if "x" in pl:
            assets["x"] = _build_x(input_value, tone, language, seed + 17)
        if "tiktok" in pl:
            assets["tiktok"] = _build_tiktok(input_value, tone, language, seed + 41)

        _ensure_niche_lock(input_value, assets)

        genes = {
            "niche": input_value,
            "keywords": _keywords(input_value),
            "angle": f"System > Trend داخل {input_value}",
            "cta": "اكتب هدفك/سؤالك وسأعيد صياغته كنظام تنفيذ",
            "tone": tone,
            "language": language,
        }

        visual = {"prompt": _visual_prompt(input_value)}
        dominance = _dominance_score(input_value, platforms, tone)

        # Create Pack (IDs in your UI look like hex => use uuid4().hex)
        pack = Pack()
        if hasattr(pack, "id"):
            pack.id = uuid.uuid4().hex
        if hasattr(pack, "mode"):
            pack.mode = mode
        if hasattr(pack, "input_value"):
            pack.input_value = input_value
        if hasattr(pack, "language"):
            pack.language = language
        if hasattr(pack, "platforms"):
            pack.platforms = platforms
        if hasattr(pack, "tone"):
            pack.tone = tone
        if hasattr(pack, "genes"):
            pack.genes = genes
        if hasattr(pack, "assets"):
            pack.assets = assets
        if hasattr(pack, "visual"):
            pack.visual = visual
        if hasattr(pack, "dominance"):
            pack.dominance = dominance
        if hasattr(pack, "sources"):
            pack.sources = {"mode": mode, "input": input_value}

        db.add(pack)
        db.flush()  # ensure pack.id exists

        # finalize job
        if hasattr(job, "pack_id"):
            job.pack_id = getattr(pack, "id", None)
        if hasattr(job, "status"):
            job.status = "done"
        if hasattr(job, "progress"):
            job.progress = 1.0
        if hasattr(job, "finished_at"):
            job.finished_at = _now()
        if hasattr(job, "updated_at"):
            job.updated_at = _now()
        if hasattr(job, "error_message"):
            job.error_message = None
        if hasattr(job, "error_trace"):
            job.error_trace = None

        db.commit()
        return {"ok": True, "job_id": str(job_id), "pack_id": getattr(pack, "id", None), "niche": input_value}

    except Exception as e:
        # Never leave job stuck in running/processing
        try:
            job = db.get(Job, str(job_id))
            if job:
                if hasattr(job, "status"):
                    job.status = "failed"
                if hasattr(job, "progress"):
                    job.progress = 0.0
                if hasattr(job, "updated_at"):
                    job.updated_at = _now()
                if hasattr(job, "finished_at"):
                    job.finished_at = _now()
                if hasattr(job, "error_message"):
                    job.error_message = str(e)
                if hasattr(job, "error_trace"):
                    job.error_trace = traceback.format_exc()
                db.commit()
        except Exception:
            pass
        return {"ok": False, "job_id": str(job_id), "error": str(e)}

    finally:
        db.close()


def worker_tick(limit: int = 1):
    """
    Optional: process queued jobs (fallback). Not required if app kicks jobs itself.
    """
    limit = max(1, min(3, int(limit or 1)))
    db = SessionLocal()
    processed = []
    try:
        q = db.query(Job).filter(Job.status == "queued").order_by(Job.created_at.asc()).limit(limit).all()
        for j in q:
            # Claim
            j.status = "running"
            if hasattr(j, "started_at"):
                j.started_at = _now()
            if hasattr(j, "updated_at"):
                j.updated_at = _now()
            if hasattr(j, "progress"):
                j.progress = 0.01
            db.commit()

            processed.append(process_build_pack(j.id))
        return {"ok": True, "processed": processed, "count": len(processed)}
    finally:
        db.close()
