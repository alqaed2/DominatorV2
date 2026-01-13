# tasks.py
from __future__ import annotations

import json
import os
import re
import time
import uuid
import hashlib
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, MetaData, Table, select, insert, update
from sqlalchemy.engine import Engine

try:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # type: ignore
except Exception:
    PG_UUID = None


# -------------------------------
# Lazy DB / Reflection utilities
# -------------------------------

_ENGINE: Optional[Engine] = None
_META: Optional[MetaData] = None
_TBL_JOBS: Optional[Table] = None
_TBL_PACKS: Optional[Table] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_db_url(url: str) -> str:
    # Render sometimes provides postgres:// which SQLAlchemy wants as postgresql://
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    db_url = _normalize_db_url(db_url)
    _ENGINE = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "3")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "2")),
        future=True,
    )
    return _ENGINE


def _reflect_tables() -> Tuple[Table, Table]:
    """
    Robustly locate jobs/packs tables even if names differ slightly.
    """
    global _META, _TBL_JOBS, _TBL_PACKS
    if _TBL_JOBS is not None and _TBL_PACKS is not None:
        return _TBL_JOBS, _TBL_PACKS

    engine = _get_engine()
    meta = MetaData()
    meta.reflect(bind=engine)
    _META = meta

    names = set(meta.tables.keys())

    def pick_table(candidates: List[str], contains: List[str]) -> Optional[str]:
        for c in candidates:
            if c in names:
                return c
        for n in names:
            low = n.lower()
            if any(k in low for k in contains):
                return n
        return None

    jobs_name = pick_table(
        candidates=["jobs", "job", "dominator_jobs", "ai_jobs"],
        contains=["job"],
    )
    packs_name = pick_table(
        candidates=["packs", "pack", "dominator_packs", "ai_packs"],
        contains=["pack"],
    )

    if not jobs_name or not packs_name:
        raise RuntimeError(f"Could not locate jobs/packs tables. Found tables: {sorted(names)[:50]}")

    _TBL_JOBS = meta.tables[jobs_name]
    _TBL_PACKS = meta.tables[packs_name]
    return _TBL_JOBS, _TBL_PACKS


def _col(table: Table, *names: str) -> Optional[str]:
    cols = {c.name.lower(): c.name for c in table.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None


def _is_uuid_column(table: Table, col_name: str) -> bool:
    col = table.columns[col_name]
    t = col.type
    name = t.__class__.__name__.lower()
    if "uuid" in name:
        return True
    if PG_UUID is not None and isinstance(t, PG_UUID):
        return True
    # some UUID types stringify like 'UUID()'
    if "uuid" in str(t).lower():
        return True
    return False


def _coerce_to_column(table: Table, col_name: str, value: Any) -> Any:
    """
    Crucial: avoid passing uuid.UUID into VARCHAR columns (causes Postgres error).
    """
    if value is None:
        return None

    if _is_uuid_column(table, col_name):
        # Column expects UUID
        if isinstance(value, uuid.UUID):
            return value
        s = str(value).strip()
        try:
            return uuid.UUID(s)
        except Exception:
            raise RuntimeError(f"Invalid UUID value for UUID column {table.name}.{col_name}: {s}")

    # Column is NOT UUID -> always return string (preserve hex IDs)
    return str(value).strip()


def _json_assign(table: Table, col_name: str, obj: Any) -> Any:
    """
    Store dict as native JSON if column type is JSON/JSONB, otherwise as string.
    """
    col = table.columns[col_name]
    tname = col.type.__class__.__name__.lower()
    if "json" in tname:
        return obj
    return json.dumps(obj, ensure_ascii=False)


# -------------------------------
# Niche-Lock Content Engine
# -------------------------------

_AR_STOP = set(
    [
        "في",
        "من",
        "على",
        "إلى",
        "عن",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "مع",
        "ثم",
        "و",
        "او",
        "أو",
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "or",
        "for",
        "in",
    ]
)


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


def _seed(niche: str, tone: str, lang: str) -> int:
    h = hashlib.sha256(f"{niche}|{tone}|{lang}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _ensure_niche_lock(niche: str, payload: Dict[str, Any]) -> None:
    niche = _clean_text(niche)
    if not niche:
        raise RuntimeError("Niche is empty (cannot generate)")
    blob = json.dumps(payload, ensure_ascii=False)
    if niche not in blob:
        kws = _keywords(niche, limit=3)
        low = blob.lower()
        if not kws or not all(k in low for k in kws):
            raise RuntimeError("Niche-Lock failed: outputs do not reflect niche")


def _build_linkedin(niche: str, tone: str, lang: str, kws: List[str], s: int) -> str:
    niche = _clean_text(niche)
    authority = "سلطة معرفية" if lang.startswith("ar") else "Authority"
    hook_variants_ar = [
        f"الخطأ الأكبر في {niche} ليس نقص الأدوات… بل اختيار الإشارة الخطأ.",
        f"إذا أردت نتائج حقيقية في {niche} خلال 14 يومًا: لا تطارد الترند… ابنِ نظام.",
        f"{niche}: 80% من الناس يعملون أكثر… ليحصلوا على أقل.",
        f"لن تكسب في {niche} لأنك أذكى… بل لأنك تقيس الشيء الصحيح.",
    ]
    hook = hook_variants_ar[s % len(hook_variants_ar)] if lang.startswith("ar") else f"{niche}: most people measure the wrong thing."
    bullets_ar = [
        "1) حدّد «عميلًا واحدًا» بدقة (ليس جمهورًا).",
        "2) اختر «عرضًا واحدًا» يمكن قياسه (قبل التوسع).",
        "3) اصنع سلسلة محتوى تقود لنقطة قرار واحدة.",
        "4) اجعل كل منشور يلتقط بيانات (سؤال/تصويت/CTA).",
    ]
    cta_ar = "سؤال مباشر: ما الجزء الأصعب لديك الآن؟ (المنتج / التسويق / التحويل / الاستمرارية)"
    hashtags = " ".join([f"#{k}" for k in kws[:5]])
    return "\n".join(
        [
            hook,
            "",
            f"الهدف هنا: تحويل {niche} إلى {authority} قابلة للتكرار.",
            "",
            *bullets_ar,
            "",
            "قاعدة ذهبية:",
            f"إذا لم تستطع شرح {niche} في جملة واحدة تُقنع شخصًا مشغولًا… فأنت لم تُصمّم الرسالة بعد.",
            "",
            cta_ar,
            "",
            hashtags,
        ]
    )


def _build_x(niche: str, tone: str, lang: str, kws: List[str], s: int) -> str:
    niche = _clean_text(niche)
    tweet_ar = [
        f"{niche}: لا تحتاج خطة معقدة… تحتاج «مقياس واحد» يمنعك من خداع نفسك.",
        f"أسرع طريقة للفشل في {niche}: تشتغل كثير وتراقب صفر مؤشرات.",
        f"في {niche}… المنافس الحقيقي ليس منافسك، بل تشتتك.",
    ]
    tweet = tweet_ar[s % len(tweet_ar)]
    thread = [
        "Thread 🧵",
        "1) اكتب الهدف بصيغة رقم + مدة (مثال: 30 طلب خلال 21 يوم).",
        "2) اختر قناة واحدة فقط لمدة أسبوعين.",
        "3) ابنِ 3 رسائل: (ألم / حل / إثبات).",
        "4) كرّر نفس الرسائل بطرق مختلفة بدل تبديل كل شيء.",
        f"5) راقب: (CTR / Replies / Saves). هذه إشارات أن {niche} بدأ يلتقط.",
        "إذا تريد، اكتب هدفك هنا وسأعيد صياغته كنظام قابل للتنفيذ.",
    ]
    hashtags = " ".join([f"#{k}" for k in kws[:4]])
    return "\n".join([tweet, "", *thread, "", hashtags])


def _build_tiktok(niche: str, tone: str, lang: str, kws: List[str], s: int) -> str:
    niche = _clean_text(niche)
    hooks = [
        f"إذا كنت داخل {niche} وتقول «الموضوع ما يمشي»… اسمع هذا.",
        f"3 أشياء تمنعك تكسب من {niche}… حتى لو أنت شاطر.",
        f"سر صغير: {niche} ليس لعبة ترند… هو لعبة نظام.",
    ]
    hook = hooks[s % len(hooks)]
    script = [
        f"Hook: {hook}",
        "مشهد 1 (2 ثواني): نص كبير على الشاشة: «السبب الحقيقي للفشل»",
        f"مشهد 2 (5 ثواني): اشرح: «أنت تحاول تعظيم كل شيء بدل تعظيم خطوة واحدة داخل {niche}»",
        "مشهد 3 (7 ثواني): قدّم إطار 3 خطوات: (عرض واضح) -> (رسالة واحدة) -> (CTA واحد)",
        "مشهد 4 (6 ثواني): مثال سريع جدًا (قبل/بعد) + إثبات بسيط",
        "Outro (3 ثواني): «اكتب كلمتك المفتاحية وسأرسل لك قالب التنفيذ»",
        "",
        "B-roll مقترح:",
        "- لقطات شاشة / كتابة على ورق / لوحة تحكم / نتائج قبل وبعد",
    ]
    return "\n".join(script)


def _build_visual_prompt(niche: str, lang: str) -> str:
    niche = _clean_text(niche)
    return (
        "Ultra-realistic cinematic professional photo, "
        f"visual metaphor for: {niche}. "
        "Modern dark studio, clean minimal tech desk, soft rim lighting, "
        "high-end advertising look, shallow depth of field, 4k, "
        "no text, no watermark, no logos."
    )


def _dominance_score(niche: str, platforms: List[str], tone: str) -> Dict[str, Any]:
    kws = _keywords(niche)
    base = 60
    if len(kws) >= 4:
        base += 10
    if "tiktok" in [p.lower() for p in platforms]:
        base += 5
    if tone.lower() in ["authority", "سلطوي", "سيادي"]:
        base += 5
    base = min(95, base)
    return {
        "score": base,
        "signals": [
            "Niche-Lock: مضمون",
            "CTA: موجود",
            "Cross-platform: مفعّل" if len(platforms) >= 2 else "منصة واحدة",
        ],
        "risk": "منخفض" if base >= 75 else "متوسط",
    }


def _make_pack_payload(niche: str, lang: str, tone: str, platforms: List[str]) -> Dict[str, Any]:
    niche = _clean_text(niche)
    kws = _keywords(niche)
    s = _seed(niche, tone, lang)

    assets: Dict[str, Any] = {}
    if "linkedin" in [p.lower() for p in platforms]:
        assets["linkedin"] = _build_linkedin(niche, tone, lang, kws, s)
    if "x" in [p.lower() for p in platforms]:
        assets["x"] = _build_x(niche, tone, lang, kws, s + 13)
    if "tiktok" in [p.lower() for p in platforms]:
        assets["tiktok"] = _build_tiktok(niche, tone, lang, kws, s + 29)

    genes = {
        "niche": niche,
        "keywords": kws,
        "angle": f"نظام > ترند داخل {niche}",
        "cta": "اكتب هدفك/سؤالك وسأعيد صياغته كنظام تنفيذ",
        "tone": tone,
        "language": lang,
    }

    dominance = _dominance_score(niche, platforms, tone)
    visual = {"prompt": _build_visual_prompt(niche, lang)}

    payload = {
        "ok": True,
        "niche": niche,
        "platforms": platforms,
        "genes": genes,
        "dominance": dominance,
        "visual": visual,
        "assets": assets,
        "pack_markdown": _pack_markdown(niche, assets, genes, dominance, visual),
        "ts": _utc_now_iso(),
    }

    _ensure_niche_lock(niche, payload)
    return payload


def _pack_markdown(
    niche: str,
    assets: Dict[str, Any],
    genes: Dict[str, Any],
    dominance: Dict[str, Any],
    visual: Dict[str, Any],
) -> str:
    parts = [
        "# Dominance Pack",
        f"**Niche:** {niche}",
        "",
        "## Genes",
        "```json",
        json.dumps(genes, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Dominance Score",
        "```json",
        json.dumps(dominance, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Visual Prompt",
        "```text",
        (visual or {}).get("prompt", ""),
        "```",
        "",
    ]
    for k, v in assets.items():
        parts.extend([f"## {k.upper()}", "```text", str(v), "```", ""])
    return "\n".join(parts)


# -------------------------------
# Job status helpers
# -------------------------------

def _set_job_status(
    conn,
    jobs: Table,
    jobs_id_col: str,
    job_id_key: Any,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    updated_at_col: Optional[str] = None,
    error_msg_col: Optional[str] = None,
    error_trace_col: Optional[str] = None,
    error_msg: Optional[str] = None,
    error_trace: Optional[str] = None,
) -> None:
    values: Dict[str, Any] = {}
    status_col = _col(jobs, "status", "state")
    progress_col = _col(jobs, "progress")

    if status_col and status is not None:
        values[status_col] = status
    if progress_col and progress is not None:
        values[progress_col] = progress
    if updated_at_col:
        values[updated_at_col] = _utc_now_iso()
    if error_msg_col is not None:
        values[error_msg_col] = error_msg
    if error_trace_col is not None:
        values[error_trace_col] = error_trace

    if values:
        conn.execute(update(jobs).where(jobs.c[jobs_id_col] == job_id_key).values(values))


# -------------------------------
# Public API expected by app.py / worker
# -------------------------------

def process_build_pack(job_id: str) -> Dict[str, Any]:
    """
    Process a single job safely:
    - locate job
    - mark processing
    - generate payload
    - insert pack
    - mark job done
    - if any error: mark job failed (never leave it stuck)
    """
    jobs, packs = _reflect_tables()
    engine = _get_engine()

    jobs_id_col = _col(jobs, "id", "job_id")
    if not jobs_id_col:
        raise RuntimeError("Jobs table has no id column")

    # IMPORTANT: coerce job_id based on actual DB column type
    job_id_key = _coerce_to_column(jobs, jobs_id_col, job_id)

    status_col = _col(jobs, "status", "state")
    updated_at_col = _col(jobs, "updated_at", "updatedAt", "ts_updated")

    req_col = _col(jobs, "request", "request_json", "payload", "params", "input")
    mode_col = _col(jobs, "mode")
    input_col = _col(jobs, "input_value", "niche", "topic", "value", "query", "prompt")
    lang_col = _col(jobs, "language", "lang")
    tone_col = _col(jobs, "tone", "voice")
    platforms_col = _col(jobs, "platforms")

    result_col = _col(jobs, "result", "result_json", "output", "response")
    error_msg_col = _col(jobs, "error_message", "error", "last_error")
    error_trace_col = _col(jobs, "error_trace", "trace", "stack")

    pack_id_in_jobs_col = _col(jobs, "pack_id", "packId")

    # Wrap everything: never leave job stuck
    try:
        with engine.begin() as conn:
            row = conn.execute(select(jobs).where(jobs.c[jobs_id_col] == job_id_key)).mappings().first()
            if not row:
                raise RuntimeError(f"Job not found: {job_id}")

            # mark processing
            if status_col:
                _set_job_status(
                    conn,
                    jobs,
                    jobs_id_col,
                    job_id_key,
                    status="processing",
                    progress=0.15,
                    updated_at_col=updated_at_col,
                    error_msg_col=error_msg_col,
                    error_trace_col=error_trace_col,
                    error_msg=None,
                    error_trace=None,
                )

            # build request dict
            req: Dict[str, Any] = {}
            if req_col and row.get(req_col) is not None:
                raw = row.get(req_col)
                if isinstance(raw, (dict, list)):
                    req = raw if isinstance(raw, dict) else {"payload": raw}
                else:
                    try:
                        req = json.loads(raw)
                    except Exception:
                        req = {"raw": str(raw)}

            mode = (req.get("mode") or (row.get(mode_col) if mode_col else None) or "niche").strip()
            niche = (
                req.get("input")
                or req.get("niche")
                or req.get("topic")
                or (row.get(input_col) if input_col else None)
                or ""
            )
            niche = _clean_text(str(niche))

            lang = (req.get("language") or req.get("lang") or (row.get(lang_col) if lang_col else None) or "ar").strip()
            tone = (req.get("tone") or (row.get(tone_col) if tone_col else None) or "Authority").strip()

            platforms_val = req.get("platforms") or (row.get(platforms_col) if platforms_col else None) or ["TikTok", "X", "LinkedIn"]
            if isinstance(platforms_val, str):
                platforms = [p.strip() for p in platforms_val.split(",") if p.strip()]
            elif isinstance(platforms_val, list):
                platforms = [str(p) for p in platforms_val]
            else:
                platforms = ["TikTok", "X", "LinkedIn"]

            payload = _make_pack_payload(niche=niche, lang=lang, tone=tone, platforms=platforms)

            # insert pack
            packs_id_col = _col(packs, "id", "pack_id")
            packs_job_id_col = _col(packs, "job_id", "jobId")
            packs_created_col = _col(packs, "created_at", "createdAt", "ts_created")
            packs_updated_col = _col(packs, "updated_at", "updatedAt", "ts_updated")

            if not packs_id_col:
                raise RuntimeError("Packs table has no id column")

            pack_uuid = uuid.uuid4()
            pack_id_value_raw = pack_uuid if _is_uuid_column(packs, packs_id_col) else pack_uuid.hex
            pack_id_value = _coerce_to_column(packs, packs_id_col, pack_id_value_raw)

            pack_row: Dict[str, Any] = {packs_id_col: pack_id_value}

            # Only set pack.job_id if compatible (prevents type mismatch)
            if packs_job_id_col:
                try:
                    pack_row[packs_job_id_col] = _coerce_to_column(packs, packs_job_id_col, job_id)
                except Exception:
                    # If packs.job_id is UUID but jobs.id is VARCHAR, skip linking to avoid failure.
                    pass

            for cname, val in [
                ("raw", payload.get("assets")),
                ("assets", payload.get("assets")),
                ("genes", payload.get("genes")),
                ("dominance", payload.get("dominance")),
                ("visual", payload.get("visual")),
                ("pack_markdown", payload.get("pack_markdown")),
                ("niche", payload.get("niche")),
            ]:
                c = _col(packs, cname, cname + "_json")
                if c:
                    pack_row[c] = _json_assign(packs, c, val)

            if packs_created_col and packs_created_col not in pack_row:
                pack_row[packs_created_col] = _utc_now_iso()
            if packs_updated_col and packs_updated_col not in pack_row:
                pack_row[packs_updated_col] = _utc_now_iso()

            conn.execute(insert(packs).values(pack_row))

            # update job done
            job_update: Dict[str, Any] = {}
            if status_col:
                job_update[status_col] = "done"
            progress_col = _col(jobs, "progress")
            if progress_col:
                job_update[progress_col] = 1.0
            if updated_at_col:
                job_update[updated_at_col] = _utc_now_iso()

            if pack_id_in_jobs_col:
                # coerce pack id to jobs.pack_id type
                job_update[pack_id_in_jobs_col] = _coerce_to_column(jobs, pack_id_in_jobs_col, pack_id_value)

            if result_col:
                job_update[result_col] = _json_assign(jobs, result_col, payload)
            if error_msg_col:
                job_update[error_msg_col] = None
            if error_trace_col:
                job_update[error_trace_col] = None

            conn.execute(update(jobs).where(jobs.c[jobs_id_col] == job_id_key).values(job_update))

        return {"ok": True, "job_id": str(job_id), "pack_id": str(pack_id_value), "niche": niche, "ts": _utc_now_iso()}

    except Exception as e:
        # Mark job as failed (never stuck)
        try:
            with engine.begin() as conn:
                _set_job_status(
                    conn,
                    jobs,
                    jobs_id_col,
                    job_id_key,
                    status="failed",
                    progress=0.0,
                    updated_at_col=updated_at_col,
                    error_msg_col=error_msg_col,
                    error_trace_col=error_trace_col,
                    error_msg=str(e),
                    error_trace=traceback.format_exc(),
                )
        except Exception:
            pass

        raise


def worker_tick(limit: int = 1) -> Dict[str, Any]:
    """
    Process up to N jobs (queued/processing/running) to rescue stuck jobs.
    Designed to run under GitHub Actions without timeouts.
    """
    limit = max(1, int(limit or 1))
    jobs, _ = _reflect_tables()
    engine = _get_engine()

    jobs_id_col = _col(jobs, "id", "job_id")
    status_col = _col(jobs, "status", "state")
    created_at_col = _col(jobs, "created_at", "createdAt", "ts_created")

    if not jobs_id_col or not status_col:
        raise RuntimeError("Jobs table missing id/status columns; cannot tick")

    processed: List[Dict[str, Any]] = []
    started = time.time()

    with engine.begin() as conn:
        q = select(jobs.c[jobs_id_col]).where(jobs.c[status_col].in_(["queued", "processing", "running"]))
        if created_at_col:
            q = q.order_by(jobs.c[created_at_col].asc())
        q = q.limit(limit)
        ids = [str(r[0]) for r in conn.execute(q).fetchall()]

    for jid in ids:
        try:
            processed.append(process_build_pack(jid))
        except Exception as e:
            processed.append({"ok": False, "job_id": jid, "error": str(e)})

    return {
        "ok": True,
        "limit": limit,
        "processed": processed,
        "took_ms": int((time.time() - started) * 1000),
        "ts": _utc_now_iso(),
    }
