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
if CORS:
    CORS(app, resources={r"/*": {"origins": "*"}})

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

    return jsonify(
        {
            "creator_id": creator_id,
            "message": f"تم إنشاء ملفك بنجاح. الوضع الافتراضي: {mode_default.capitalize()}",
            "mode_default": mode_default,
        }
    )


@app.post("/v1/daily-brief")
def daily_brief():
    data = _require_json()
    creator_id = data.get("creator_id")
    n_ideas = int(data.get("n_ideas") or 3)

    if not creator_id:
        return jsonify({"error": "creator_id مطلوب"}), 400

    creator = _get_creator(creator_id)
    if not creator:
        return jsonify({"error": "creator_id غير موجود. نفّذ /v1/onboard أولًا أو ثبّت قاعدة البيانات على Disk."}), 404

    ideas = _generate_ideas(creator, n=n_ideas)
    return jsonify({"creator_id": creator_id, "ideas": ideas})


@app.post("/v1/build-pack")
def build_pack():
    data = _require_json()

    creator_id = data.get("creator_id")
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

    return jsonify(result)


@app.post("/v1/submit-metrics")
def submit_metrics():
    data = _require_json()
    creator_id = data.get("creator_id")
    experiment_id = data.get("experiment_id")
    payload = data.get("metrics") or data.get("payload") or data

    if not creator_id or not experiment_id:
        return jsonify({"error": "creator_id و experiment_id مطلوبين"}), 400

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

    return jsonify({"status": "ok", "metric_id": metric_id})


@app.get("/v1/report/<experiment_id>")
def report(experiment_id: str):
    creator_id = request.args.get("creator_id")
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب كـ query param"}), 400

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
