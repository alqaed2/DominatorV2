import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(24))

# قاموس المعرفة الاستراتيجي للبنية واللغة
SPEC_CONFIG = {
    "dimensions": "Aspect Ratio 9:16 (for TikTok/Reels)",
    "tags": {
        "ar": ["#تكنولوجيا", "#ذكاء_اصطناعي", "#مستقبل_الربح", "#ترند"],
        "en": ["#TechEdge", "#AILeadership", "#ProfitableFuture", "#GrowthMatrix"]
    }
}

# محرك مطالبات (VEO3) بفرض الأبعاد ونظام الإخراج المتطور
def generate_prompt_for_veo3(segment, language="en"):
    ar_constraint = "Aspect ratio 9:16, suitable for TikTok, ultra-high vertical resolution."
    visual_fidelity = "Sharp cinematographic edges, focus on subject centers, fast-paced visuals."
    return (
        f"Masterpiece Scene: {segment}. {ar_constraint}. Rendering: 8K Vertical, Cinematic lighting. "
        f"Mood: Suspenseful/Futuristic. Visuals: {visual_fidelity}"
    )

# المخدم الرئيسي للمحتوى المتعدد للغات بالوقت الفعلي
def get_localized_pack(subject, lang="ar"):
    if lang == "ar":
        hook = f"هل تتوقع أن يختفي مجال {subject} بحلول 2045؟ أم أنها مجرد بداية الهراء الرقمي؟! 🚀"
        script = (
             f"العالم يتغير أسرع مما يمكنك الرمش بجفنيك. الحديث عن {subject} الآن ليس "
             f"مجرد فضول، بل هو البواب بين الربح والبقاء. المهيمنون ليس لديهم قلوب؛ لديهم أنظمة. هل أنت مستعد للسيطرة؟"
        )
        caption = f"الأسرار العميقة لـ {subject}. المستقبل يطلب انضمامك. 🌍"
    else:
        # Default Logic for High-Speed English (EN)
        hook = f"Could {subject} be the reason you're failing right now? 🚨 Take five seconds to witness history."
        script = (
            f"The tectonic plates of {subject} are shifting. In minutes from now, what you knew about "
            f"the digital world is moot. You need technical dominance. Be the architect, not the brick."
        )
        caption = f"Unconventional truths of {subject}. Read if you dare. 👁️"
    
    return hook, script, caption

@app.route("/")
@app.route("/dashboard")
def index():
    return render_template("index.html")

@app.route("/v1/session", methods=["GET"])
def get_session():
    uid = "CREATOR_" + secrets.token_hex(4).upper()
    return jsonify({"success": True, "creator_id": uid})

@app.route("/v1/build-pack", methods=["POST"])
def build_pack():
    data = request.json
    subject = data.get("subject", "Global Control")
    requested_lang = data.get("lang", "en") # افتراضياً إنجليزي لضمان التغطية العالمية

    # بناء الجوهر المتعدد لغات
    hook, script, caption = get_localized_pack(subject, requested_lang)
    
    # تفريغ الأجزاء للحياة البصرية العمودية المذهلة
    segments = [
        f"Wide vertical tilt of futuristic energy flowing through {subject}",
        f"A cybernetic gaze interpreting complex data streams for {subject} in center frame",
        f"Rapid transition of advanced high-tech tools interacting with human shadows"
    ]
    
    veo_set = []
    for s_step in segments:
        veo_set.append({
            "veo_prompt": generate_prompt_for_veo3(s_step, requested_lang),
            "v_length": "7-10s Vertical"
        })

    # دبلجة الهاشتاجات المواتية لروح العصر
    tag_list = " ".join(SPEC_CONFIG["tags"].get(requested_lang, SPEC_CONFIG["tags"]["en"]))

    payload = {
        "status": "Targeting 9:16 Viral Hub",
        "pack": {
            "hooks": hook,
            "script": script,
            "caption": f"{caption} \n\n {tag_list}",
            "visuals": veo_set
        }
    }
    
    return jsonify(payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
