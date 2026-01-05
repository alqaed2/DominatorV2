import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
# جدران الحماية والهيكلية (Supreme Strength Integration)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(24))

# قاموس التوجهات العالمية (Trend Engine Knowledge)
MARKET_KNOWLEDGE = {
    "topics": ["Ai Technology", "Wealth Gap 2026", "Digital Business", "Lifestyle Luxury"],
    "tags": ["#FutureShorts", "#ViralLogic", "#AIPioneers", "#TechRevolution"]
}

# مصنع البث والمطالبات (The Cinematic Logic Engine)
def generate_prompt_for_veo3(script_segment):
    """
    تحويل سكريبت عادي لمطالب مخرج سينمائي (Director Level Prompting)
    """
    return (
        f"Masterpiece, cinematic aesthetic, 8K ultra-wide. Scene: {script_segment}. "
        f"Camera: Pan-right with dynamic tracking. Environment: Hyper-realistic lighting, Volumetric lights. "
        f"Motion: 60fps steadycam. ArtStyle: Professional Vlog/Sci-fi tech documentary."
    )

@app.route("/")
@app.route("/dashboard")
def index():
    return render_template("index.html")

@app.route("/v1/session", methods=["GET"])
def get_session():
    # سياسة الـ Zero login للنمو الفيروسي
    guest_id = "DOM_" + secrets.token_hex(6).upper()
    return jsonify({"success": True, "creator_id": guest_id})

@app.route("/v1/build-pack", methods=["POST"])
def build_pack():
    data = request.json
    subject = data.get("subject", "General AI Concept")
    
    # 1. نظام الـ Hook الخطير (7 ثوان الأولى السيادية)
    hook = f"Is the {subject} dying? Or are you just behind?! 🚀"
    
    # 2. السكريبت المقاتل للهرب من الروتين
    script_content = (
        f"In year 2026, the obsession with {subject} has reached a peak level. "
        f"Experts explain that what we ignored yesterday, dominates us today. "
        f"Forget traditional ways; we use pure AI dominance to evolve. Follow our lead!"
    )
    
    # تفكيك العوالم لتناسب VEO3 ببراعة (The Chrono-Slice Algorithm)
    segments = [
        "Dynamic high-tech office showing glowing hologram screens",
        "A focused innovator gazing into digital data streams in POV shot",
        "Fast-cutting futuristic cities visualizing the speed of progress"
    ]
    
    veo3_prompts = []
    for seg in segments:
        vebuilt = {
            "scene": seg,
            "veo_prompt": generate_prompt_for_veo3(seg),
            "v_length": "8s"
        }
        veo3_prompts.append(vebuilt)

    # 3. خطة النشر والهيمنة الذكية
    final_output = {
        "is_viral": True,
        "content_pack": {
            "v3_logic": veo3_prompts,
            "hook": hook,
            "script": script_content,
            "hashtags": " ".join(MARKET_KNOWLEDGE["tags"]),
            "caption": f"Unlocking deep secrets about {subject}. 🌍 #DominantTech"
        }
    }
    
    return jsonify(final_output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
