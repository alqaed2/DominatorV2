import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(24))

def get_optimized_data(subject, lang):
    """صانع المحتوى المسلح: يجمع الفلسفة الإخراجية واللغة"""
    aspect = "Vertical 9:16 optimized for Social Media (TikTok/High Definition Cinematic)."
    
    if lang == "ar":
        content = {
            "hook": f"سر الهيمنة في مجال {subject} بحلول عام 2026! 🚀",
            "val_script": f"في أعماق السوق الرقمي، يتصدر {subject} الواجهة. لا أحد يخبرك كيف تسيطر على الخوارزميات، لكن السيكولوجيا واضحة: الجذب أو الاندثار. التجهيز يبدأ الآن بلغة القوة.",
            "val_caption": f"خطة الهيمنة لـ {subject}. المستقبل للمبادئين ومهندسي الأنظمة. 🌎",
            "val_tags": "#تقاعد_تقني #نمو #المركز #أدوات_فجوة",
            "scenes": [
                f"Close up lens: High-depth detail of symbols from {subject} era. Center weighted composition.",
                f"Establishing shot: Massive tech infrastructure reacting to {subject}, neon blue lights flare.",
                f"Point of view: Interaction with virtual glass interface designing the future of {subject}."
            ]
        }
    else:
        content = {
            "hook": f"Everyone ignored {subject} until now. Are you waiting for a crash? 🌋",
            "val_script": f"The tectonic landscape of {subject} is redefined tonight. Don't play the game, rebuild the rules from the ground up to guarantee algorithmic dominance. Success is inevitable when architecture is flawless.",
            "val_caption": f"Executing Phase One for {subject}. Stay Dominant. 👁️⚡",
            "val_tags": "#AlphaFocus #DigitalAscension #TrendSurfing #LegacyBuild",
            "scenes": [
                f"Dynamic crane-to-portrait focus of an elite laboratory relating to theme: {subject}.",
                f"Macro visuals of pulsating power sources shifting to represent theme values of {subject}.",
                f"Cinematic focus on an intense sunrise overlaid with raw data flowing centered for TikTok style."
            ]
        }

    modified_scenes = [f"{s} | PROMPT SPECS: {aspect}, Cinematic colors, 8K ultra detail." for s in content["scenes"]]
    
    return {
        "is_arabic": (lang == "ar"),
        "hook": content["hook"],
        "script": content["val_script"], 
        "caption": content["val_caption"],
        "tags": content["val_tags"],
        "prompts": modified_scenes
    }

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/v1/build", methods=["POST"])
def build_engine():
    try:
        data = request.json
        subject = data.get("subject", "Alpha Control")
        lang = data.get("lang", "en")
        response = get_optimized_data(subject, lang)
        return jsonify(response)
    except:
        return jsonify({"error": "System Malfunction"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
