import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, request, render_template, send_from_directory

# Optional CORS
try:
    from flask_cors import CORS
except Exception:
    CORS = None


APP_DIR = os.path.dirname(os.path.abspath(__file__))

# مهم: اجعل DB_PATH قابل للتغيير من Render Environment
# لو ركبت Persistent Disk في Render على /var/data استخدم:
# DB_PATH=/var/data/dominator.db
DB_PATH = os.getenv("DB_PATH", os.path.join(APP_DIR, "data", "dominator.db"))

SERVICE_NAME = os.getenv("SERVICE_NAME", "AI_DOMINATOR_TikTok_First")
ALLOW_ANON_BUILD_PACK = os.getenv("ALLOW_ANON_BUILD_PACK", "1") == "1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_db_dir() -> None:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


def _db() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS creators (
                creator_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                display_name TEXT,
                goal TEXT,
                primary_niche TEXT,
                sub_niches_json TEXT,
                language TEXT,
                tone TEXT,
                constraints_json TEXT,
                tiktok_profile_url TEXT,
                mode_default TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                idea_title TEXT,
                angle TEXT,
                value_promise TEXT,
                preferred_length_sec INTEGER,
                mode TEXT,
                result_json TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )

        conn.commit()


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _json_loads(s: str) -> Any:
    return json.loads(s) if s else None


def _get_creator(creator_id: str) -> Optional[Dict[str, Any]]:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM creators WHERE creator_id = ?",
            (creator_id,),
        ).fetchone()

    return dict(row) if row else None



def _resolve_creator_id(payload: dict | None = None) -> str | None:
    """Resolve creator_id from body/header/query/cookie (in that order)."""
    cid = None
    if isinstance(payload, dict):
        cid = payload.get("creator_id") or payload.get("creatorId") or payload.get("creatorID")
    cid = cid or request.headers.get("X-Creator-Id") or request.headers.get("x-creator-id")
    cid = cid or request.args.get("creator_id") or request.args.get("creatorId")
    cid = cid or request.cookies.get("creator_id")
    if isinstance(cid, str):
        cid = cid.strip()
    return cid or None


def _normalize_lang(lang: str | None) -> str:
    if not isinstance(lang, str) or not lang.strip():
        return "en"
    lang = lang.strip()
    # Accept-Language can be: "ar-YE,ar;q=0.9,en;q=0.8"
    lang = lang.split(",")[0].strip()
    lang = lang.split("-")[0].strip().lower()
    return lang or "en"


def _ensure_creator(payload: dict | None = None, *, allow_auto_create: bool = True) -> dict:
    """
    Return a valid creator record.
    - If creator_id exists: load it.
    - If missing/unknown and allow_auto_create: create a minimal creator and return it.
    """
    cid = _resolve_creator_id(payload)
    if cid:
        creator = _get_creator(cid)
        if creator is not None:
            return creator

    if not allow_auto_create:
        raise ValueError("creator_id غير موجود")

    # Auto-create (UI-friendly): the UI can store this creator_id in localStorage or cookie.
    creator_id = _create_creator_id()
    lang = _normalize_lang(
        (payload or {}).get("language")
        or request.headers.get("X-Lang")
        or request.headers.get("Accept-Language")
    )

    profile = {
        "display_name": (payload or {}).get("display_name") or "Creator",
        "primary_niche": (payload or {}).get("primary_niche") or "general",
        "primary_language": lang,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _upsert_creator(creator_id, profile)
    return _get_creator(creator_id)

def _upsert_creator(creator: Dict[str, Any]) -> None:
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO creators (
                creator_id, created_at, display_name, goal, primary_niche,
                sub_niches_json, language, tone, constraints_json,
                tiktok_profile_url, mode_default
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creator_id) DO UPDATE SET
                display_name=excluded.display_name,
                goal=excluded.goal,
                primary_niche=excluded.primary_niche,
                sub_niches_json=excluded.sub_niches_json,
                language=excluded.language,
                tone=excluded.tone,
                constraints_json=excluded.constraints_json,
                tiktok_profile_url=excluded.tiktok_profile_url,
                mode_default=excluded.mode_default
            """,
            (
                creator.get("creator_id"),
                creator.get("created_at") or _utc_now_iso(),
                creator.get("display_name"),
                creator.get("goal"),
                creator.get("primary_niche"),
                creator.get("sub_niches_json"),
                creator.get("language"),
                creator.get("tone"),
                creator.get("constraints_json"),
                creator.get("tiktok_profile_url"),
                creator.get("mode_default"),
            ),
        )
        conn.commit()


def _require_json() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _score_hook(hook_text: str) -> Tuple[float, List[str]]:
    """
    سكور بسيط (0-100) + أسباب.
    الهدف: يعطيك ترتيب سريع A/B/C بدون تعقيد.
    """
    reasons: List[str] = []
    text = (hook_text or "").strip()

    if not text:
        return 0.0, ["هوك فارغ."]

    # طول مثالي تقريبًا 6-14 كلمة
    words = [w for w in text.split() if w.strip()]
    wc = len(words)
    score = 60.0

    if 6 <= wc <= 14:
        score += 18
        reasons.append("طول مناسب لأول 1–2 ثانية.")
    elif wc < 6:
        score -= 10
        reasons.append("قصير جدًا؛ قد لا يوضح الوعد بسرعة.")
    else:
        score -= 8
        reasons.append("طويل نسبيًا؛ قد يقلل من سرعة الالتقاط.")

    # محفزات الفضول
    triggers = ["خطأ", "3", "سر", "صادم", "بدون", "في أقل", "خلال", "دقيقة", "ثانية", "لا تفعل"]
    hit = sum(1 for t in triggers if t in text)
    if hit >= 1:
        score += min(12, hit * 4)
        reasons.append("فيه محفز فضول/قائمة/وعد واضح.")

    # علامات الإيقاع
    if "…" in text or "..." in text or "؟" in text:
        score += 4
        reasons.append("استخدام (Open Loop) أو سؤال يعزز الاستمرار.")

    score = max(0.0, min(100.0, score))
    return float(round(score, 2)), reasons


def _build_hooks(primary_niche: str, angle: str) -> Dict[str, Dict[str, str]]:
    niche = primary_niche or "مجالك"
    return {
        "A": {
            "hook_text": f"إذا كنت في {niche} وتفعل هذا… فأنت تخسر بدون أن تدري.",
            "onscreen_text": f"توقف عن هذا في {niche}!",
        },
        "B": {
            "hook_text": f"3 أخطاء تمنعك من التقدم في {niche}… رقم 2 صادم.",
            "onscreen_text": "3 أخطاء قاتلة",
        },
        "C": {
            "hook_text": f"في أقل من 30 ثانية… طريقة عملية لتحسن نتيجتك في {niche}.",
            "onscreen_text": "طريقة خلال 30 ثانية",
        },
    }


def _generate_ideas(creator: Dict[str, Any], n: int = 3) -> List[Dict[str, Any]]:
    primary_niche = creator.get("primary_niche") or "مجالك"

    angles = [
        ("تفكيك خطأ + بديل عملي", f"خطأ شائع يمنعك من النجاح في {primary_niche}", "خطوة واحدة تصحح المسار خلال يوم واحد."),
        ("قائمة خطوات قابلة للحفظ", f"3 خطوات سريعة لتحسين نتائجك في {primary_niche}", "خطة بسيطة: نفّذ، قِس، عدّل."),
        ("سبب جذري + علاج مباشر", f"السبب الحقيقي لعدم تقدمك في {primary_niche} (والحل)", "تغيير صغير يرفع نتائجك بشكل ملحوظ."),
    ]

    out: List[Dict[str, Any]] = []
    for angle, title, value_promise in angles[: max(1, n)]:
        hooks = _build_hooks(primary_niche, angle)
        variants = []
        for key in ["A", "B", "C"]:
            score, why = _score_hook(hooks[key]["hook_text"])
            variants.append(
                {
                    "key": key,
                    "hook_text": hooks[key]["hook_text"],
                    "onscreen_text": hooks[key]["onscreen_text"],
                    "minimum_fix": "أضف CTA واحدًا واضحًا: (اكتب كلمة X بالتعليقات) أو (احفظ الفيديو لقائمة الخطوات).",
                    "score": score,
                    "why": why,
                }
            )

        out.append(
            {
                "angle": angle,
                "title": title,
                "value_promise": value_promise,
                "variants": variants,
            }
        )

    return out


def _build_pack(creator: Dict[str, Any], idea_title: str, angle: str, value_promise: str, preferred_length_sec: int, mode: str) -> Dict[str, Any]:
    primary_niche = creator.get("primary_niche") or "مجالك"
    hooks = _build_hooks(primary_niche, angle)

    # سكور hooks
    scores = {}
    why_map = {}
    for k in ["A", "B", "C"]:
        sc, why = _score_hook(hooks[k]["hook_text"])
        scores[k] = sc
        why_map[k] = why

    # اختَر الأفضل تلقائيًا كـ default hook داخل السكربت
    best_key = max(scores, key=lambda kk: scores[kk])
    best_hook = hooks[best_key]["hook_text"]
    best_onscreen = hooks[best_key]["onscreen_text"]

    # سكربت (قابل للتسجيل)
    script = "\n".join(
        [
            best_hook,
            f"معظم الناس في {primary_niche} يقعوا في خطأ واحد…",
            "الحل في 3 خطوات: (1) حدد الهدف بدقة، (2) نفّذ خطوة واحدة اليوم، (3) راقب النتيجة وعدّل.",
            "اكتب كلمة (جاهز) بالتعليقات وسأرسل لك الخطوات بشكل أوضح.",
        ]
    )

    srt = "\n".join(
        [
            "1",
            "00:00:00,000 --> 00:00:02,000",
            "{HOOK}",
            "",
            "2",
            "00:00:02,000 --> 00:00:08,000",
            f"معظم الناس في {primary_niche} يقعوا في خطأ واحد…",
            "",
            "3",
            "00:00:08,000 --> 00:00:22,000",
            "الحل في 3 خطوات: (1) حدد الهدف بدقة، (2) نفّذ خطوة واحدة اليوم، (3) راقب النتيجة وعدّل.",
            "",
            "4",
            "00:00:22,000 --> 00:00:28,000",
            "اكتب كلمة (جاهز) بالتعليقات وسأرسل لك الخطوات بشكل أوضح.",
        ]
    )

    experiment_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    payload_ready = {
        "id": artifact_id,
        "title": idea_title,
        "keywords": [primary_niche, "نصائح"],
        "hooks": hooks,
        "script_teleprompter": script,
        "onscreen_text_srt": srt,
        "caption": f"{value_promise}\n# {primary_niche}",
        "hashtags": [f"#{primary_niche.replace(' ', '')}", "#تعلم", "#نصائح"],
        "edit_cues": [
            "تغيير لقطة/زووم بسيط كل 1.5–2 ثانية.",
            "أظهر الكلمات المفتاحية على الشاشة.",
            "اجعل الـHook بصوت قوي + نص كبير.",
        ],
        "shot_list": [
            "لقطة قريبة للوجه/المتحدث مع إضاءة جيدة.",
            "B-roll بسيط أثناء ذكر الخطوات.",
            "لقطة ختام مع CTA على الشاشة.",
        ],
        "timeline": {
            "video_seconds": int(preferred_length_sec or 28),
            "sections": [
                {"type": "hook", "t_start": 0, "t_end": 2, "text": best_hook, "onscreen": best_onscreen},
                {"type": "problem", "t_start": 2, "t_end": 8, "text": f"معظم الناس في {primary_niche} يقعوا في خطأ واحد…", "onscreen": "الخطأ الشائع"},
                {"type": "solution", "t_start": 8, "t_end": 22, "text": "الحل في 3 خطوات: (1) حدد الهدف بدقة، (2) نفّذ خطوة واحدة اليوم، (3) راقب النتيجة وعدّل.", "onscreen": "الحل (3 خطوات)"},
                {"type": "cta", "t_start": 22, "t_end": 28, "text": "اكتب كلمة (جاهز) بالتعليقات وسأرسل لك الخطوات بشكل أوضح.", "onscreen": "اكتب (جاهز) 👇"},
            ],
        },
    }

    payload_experiment_plan = {
        "what_to_test": [
            "Hook A/B/C (أول 1-2 ثانية)",
            "Length (قصير/متوسط عند الحاجة)",
            "Caption keywords + On-screen text",
            "Audio (Trending vs Original إذا كان مناسبًا)",
        ],
        "measurement_points": ["T+60m", "T+24h", "T+48h"],
        "win_function": {
            "phase_1": ["views_velocity (60-180m)", "shares_per_1k_views"],
            "phase_2": ["comments_per_1k_views", "engagement_rate", "follow_rate_if_available"],
        },
        "next_best_action": "إذا فاز Variant ما: اصنع Part 2 بنفس الزاوية مع تطعيم معلومة جديدة.",
    }

    payload_prompt_pack = {
        "title": idea_title,
        "prompts": {
            "hooks": f"ولّد 3 Hooks مختلفة (A/B/C) عن {idea_title}، كل Hook <= 14 كلمة، مع نص شاشة قصير.",
            "script": f"اكتب سكربت TikTok ({preferred_length_sec} ثانية) عن: {idea_title} بزاوية: {angle} وبقيمة: {value_promise}. ابدأ بهوك قوي خلال 1 ثانية.",
            "editing": "اقترح إرشادات مونتاج سريع: تقطيع، تكبير، نص على الشاشة كل 1-2 ثانية، مع إيقاع عالي.",
            "visual": "اقترح شكل بصري للـFrame الأول + نص كبير واضح + ألوان متناسقة.",
            "next_series": "اقترح 5 أفكار (Part 2/3/4) مبنية على نفس الزاوية لتعزيز سلسلة محتوى.",
        },
    }

    result = {
        "experiment_id": experiment_id,
        "predicted": {
            "note": "اختبر Hooks A/B/C للحصول على دليل نتيجة (Lift).",
            "scores": scores,
        },
        "artifacts": [
            {"type": "ready_to_record_kit", "payload": payload_ready},
            {"type": "experiment_plan", "payload": payload_experiment_plan},
            {"type": "prompt_pack", "payload": payload_prompt_pack},
        ],
    }

    return result


app = Flask(__name__, template_folder="templates", static_folder="static")
# Ensure UTF-8 JSON output (Arabic-safe)
try:
    app.json.ensure_ascii = False
except Exception:
    pass
app.config["JSON_AS_ASCII"] = False

if CORS:
    CORS(app, resources={r"/*": {"origins": "*"}})

@app.after_request
def _add_utf8_headers(resp):
    # Make sure JSON responses declare UTF-8 (helps some clients/console tools)
    try:
        if resp.mimetype == "application/json" and "charset" not in (resp.content_type or "").lower():
            resp.content_type = resp.content_type + "; charset=utf-8"
    except Exception:
        pass
    return resp

from services.trends_api import trends_bp
app.register_blueprint(trends_bp)

_init_db()


@app.get("/")
def home():
    # صفحة UI بسيطة لتجربة POST من المتصفح
    return render_template("index.html")


@app.get("/favicon.ico")
def favicon():
    # منع ضوضاء 404 في الكونسل
    return ("", 204)


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": SERVICE_NAME,
            "time": _utc_now_iso(),
            "db_path": DB_PATH,
        }
    )


@app.get("/api")
def api_index():
    # JSON سريع للاندبوينتس (لو تحب)
    return jsonify(
        {
            "status": "ok",
            "service": SERVICE_NAME,
            "endpoints": {
                "health": "GET /health",
                "ui": "GET /",
                "onboard": "POST /v1/onboard",
            "session": "GET|POST /v1/session",
                "daily_brief": "POST /v1/daily-brief",
                "build_pack": "POST /v1/build-pack",
                "submit_metrics": "POST /v1/submit-metrics",
                "report": "GET /v1/report/<experiment_id>?creator_id=...",
            },
        }
    )


@app.post("/v1/onboard")
def onboard():
    data = _require_json()

    display_name = data.get("display_name")
    goal = data.get("goal")
    primary_niche = data.get("primary_niche")
    sub_niches = data.get("sub_niches") or []
    language = data.get("language", "ar")
    tone = data.get("tone", "educational")
    constraints = data.get("constraints") or {}
    tiktok_profile_url = data.get("tiktok_profile_url")

    if not display_name or not goal or not primary_niche:
        return jsonify({"error": "حقول مطلوبة: display_name, goal, primary_niche"}), 400

    creator_id = str(uuid.uuid4())
    mode_default = "manual" if not tiktok_profile_url else "linked"

    creator = {
        "creator_id": creator_id,
        "created_at": _utc_now_iso(),
        "display_name": display_name,
        "goal": goal,
        "primary_niche": primary_niche,
        "sub_niches_json": _json_dumps(sub_niches),
        "language": language,
        "tone": tone,
        "constraints_json": _json_dumps(constraints),
        "tiktok_profile_url": tiktok_profile_url,
        "mode_default": mode_default,
    }
    _upsert_creator(creator)

    resp = jsonify(
        {
            "creator_id": creator_id,
            "message": f"تم إنشاء ملفك بنجاح. الوضع الافتراضي: {mode_default.capitalize()}",
            "mode_default": mode_default,
        }
    )
    resp.set_cookie("creator_id", creator_id, max_age=60 * 60 * 24 * 365, samesite="Lax", secure=True)
    return resp


@app.post("/v1/daily-brief")
def daily_brief():
    data = _require_json()
    n_ideas = int(data.get("n_ideas") or 3)

    try:
        creator = _ensure_creator(data, allow_auto_create=True)
        creator_id = creator.get("id")
    except Exception:
        return jsonify({"error": "تعذر إنشاء جلسة المستخدم"}), 400

    ideas = _generate_ideas(creator, n=n_ideas)
    resp = jsonify({"creator_id": creator_id, "ideas": ideas})
    try:
        if creator_id:
            resp.set_cookie("creator_id", creator_id, max_age=60 * 60 * 24 * 365, samesite="Lax", secure=True)
    except Exception:
        pass
    return resp
@app.get("/v1/session")
def get_session():
    """
    UI helper: get (or create) a creator session id.
    The UI can store creator_id in localStorage; we also set a cookie for convenience.
    """
    creator = None
    cid = _resolve_creator_id(None)
    if cid:
        creator = _get_creator(cid)

    created = False
    if creator is None:
        creator = _ensure_creator({}, allow_auto_create=True)
        created = True

    resp = jsonify({
        "creator_id": creator.get("id"),
        "created": created,
        "profile": {
            "display_name": creator.get("display_name"),
            "primary_niche": creator.get("primary_niche"),
            "primary_language": creator.get("primary_language"),
        },
    })
    # Cookie is optional, but it removes the need to keep passing creator_id manually.
    resp.set_cookie("creator_id", creator.get("id"), max_age=60 * 60 * 24 * 365, samesite="Lax", secure=True)
    return resp


@app.post("/v1/session")
def post_session():
    """
    Create or update a session.
    If you pass an existing creator_id (header/body/query/cookie) we update its profile.
    Otherwise we create a new creator and return its id.
    """
    data = request.get_json(silent=True) or {}
    cid = _resolve_creator_id(data)
    creator = _get_creator(cid) if cid else None

    if creator is None:
        creator = _ensure_creator(data, allow_auto_create=True)
        created = True
    else:
        created = False
        # Optional profile update from UI (kept minimal)
        updates = {}
        for k in ("display_name", "primary_niche", "primary_language"):
            if k in data and isinstance(data[k], str) and data[k].strip():
                updates[k] = data[k].strip()
        if updates:
            _upsert_creator(creator.get("id"), updates)
            creator = _get_creator(creator.get("id"))

    resp = jsonify({"creator_id": creator.get("id"), "created": created, "status": "ok"})
    resp.set_cookie("creator_id", creator.get("id"), max_age=60 * 60 * 24 * 365, samesite="Lax", secure=True)
    return resp

@app.post("/v1/build-pack")
def build_pack():
    data = _require_json()

    try:
        creator = _ensure_creator(data, allow_auto_create=True)
        creator_id = creator.get("id")
    except Exception:
        return jsonify({"error": "تعذر إنشاء جلسة المستخدم"}), 400
    idea_title = data.get("idea_title")
    angle = data.get("angle")
    value_promise = data.get("value_promise")
    preferred_length_sec = int(data.get("preferred_length_sec") or 28)
    mode = data.get("mode") or "both"

    if not creator_id:
        return jsonify({"error": "creator_id مطلوب"}), 400
    if not idea_title or not angle or not value_promise:
        return jsonify({"error": "حقول مطلوبة: idea_title, angle, value_promise"}), 400

    creator = _get_creator(creator_id)

    # خيار إنقاذ: لو DB اتصفّر بعد Deploy، اسمح بإنشاء Creator افتراضي
    if not creator and ALLOW_ANON_BUILD_PACK:
        creator = {
            "creator_id": creator_id,
            "created_at": _utc_now_iso(),
            "display_name": "Creator",
            "goal": "followers",
            "primary_niche": "التسويق الرقمي",
            "sub_niches_json": _json_dumps([]),
            "language": "ar",
            "tone": "educational",
            "constraints_json": _json_dumps({}),
            "tiktok_profile_url": None,
            "mode_default": "manual",
        }
        _upsert_creator(creator)

    if not creator:
        return jsonify({"error": "creator_id غير موجود. نفّذ /v1/onboard أولًا."}), 404

    result = _build_pack(creator, idea_title, angle, value_promise, preferred_length_sec, mode)

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO experiments (
                experiment_id, created_at, creator_id,
                idea_title, angle, value_promise, preferred_length_sec, mode,
                result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["experiment_id"],
                _utc_now_iso(),
                creator_id,
                idea_title,
                angle,
                value_promise,
                preferred_length_sec,
                mode,
                _json_dumps(result),
            ),
        )
        conn.commit()
    resp = jsonify(result)
    try:
        if creator_id:
            resp.set_cookie("creator_id", creator_id, max_age=60 * 60 * 24 * 365, samesite="Lax", secure=True)
    except Exception:
        pass
    return resp
@app.post("/v1/submit-metrics")
def submit_metrics():
    data = _require_json()
    experiment_id = data.get("experiment_id")
    try:
        creator = _ensure_creator(data, allow_auto_create=True)
        creator_id = creator.get("id")
    except Exception:
        creator_id = None
    payload = data.get("metrics") or data.get("payload") or data
    if not experiment_id:
        return jsonify({"error": "experiment_id مطلوب"}), 400
    if not creator_id:
        # Last resort: create a session so metrics can still be recorded.
        creator = _ensure_creator({}, allow_auto_create=True)
        creator_id = creator.get("id")

    metric_id = str(uuid.uuid4())
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO metrics (id, created_at, experiment_id, creator_id, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (metric_id, _utc_now_iso(), experiment_id, creator_id, _json_dumps(payload)),
        )
        conn.commit()
    resp = jsonify({"status": "ok", "metric_id": metric_id})
    try:
        if creator_id:
            resp.set_cookie("creator_id", creator_id, max_age=60 * 60 * 24 * 365, samesite="Lax", secure=True)
    except Exception:
        pass
    return resp
@app.get("/v1/report/<experiment_id>")
def report(experiment_id: str):
    creator_id = _resolve_creator_id(None) or request.args.get("creator_id")
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب (query/header/cookie)"}), 400

    with _db() as conn:
        exp = conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ? AND creator_id = ?",
            (experiment_id, creator_id),
        ).fetchone()

        if not exp:
            return jsonify({"error": "experiment_id غير موجود لهذا creator_id"}), 404

        metrics_rows = conn.execute(
            "SELECT * FROM metrics WHERE experiment_id = ? AND creator_id = ? ORDER BY created_at ASC",
            (experiment_id, creator_id),
        ).fetchall()

    result = _json_loads(exp["result_json"])
    metrics = [{"id": r["id"], "created_at": r["created_at"], "payload": _json_loads(r["payload_json"])} for r in metrics_rows]

    return jsonify(
        {
            "experiment_id": experiment_id,
            "creator_id": creator_id,
            "created_at": exp["created_at"],
            "result": result,
            "metrics": metrics,
        }
    )


# For local debugging: python app.py
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=True)

