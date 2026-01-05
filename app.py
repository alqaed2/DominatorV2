import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(24))

def get_cinematic_director_notes():
    """حقن تعليمات التكوين السينمائي الرأسي الفائق لـ VEO3"""
    return (
        "Aspect ratio 9:16, centered composition for TikTok vertical flow. "
        "Dynamic high-frequency lighting, cinematic depth, fluid motion. "
        "Unreal Engine 5 style hyper-clarity. Directed by AI DominatorV2 Master UI."
    )

def generate_full_content(subject, lang):
    notes = get_cinematic_director_notes()
    
    if lang == "ar":
        hook = f"صناعة {subject} كانت مجرد هواية، اليوم هي سلاح السيطرة الصامت! 🕵️"
        script = (
            f"في ظلال العصر الرقمي، {subject} هي المحرك الجديد للثروات. "
            f"البحث عن التميز انتهى هنا. اتبع المسار المهندس لبناء هيمنتك الخاصة."
        )
        caption = f"خارطة طريق لـ {subject} الحقيقية. انضم للمستقبل. 🌎"
        tags = "#ذكاء_اصطاني #هيمنة_رقمية #سعودي_تك #مستقبل"
        scenes = [
            f"Dramatic close-up vertical tracking of {subject} concepts into futuristic light",
            "Wide angle vertical showcase of a bustling cyberpunk city focus on subject",
            "Slow motion focus on a mastermind looking into holographic maps representing the dream"
        ]
    else:
        hook = f"Stopping you for a second: {subject} is rebalancing the ecosystem. Are you ready?"
        script = (
            f"Welcome to the aftermath of {subject}. In this high-tension journey, we decode success architectures. "
            f"Efficiency isn't enough; search for absolute dominance."
        )
        caption = f"Decoding survival with {subject}. Rise above the clutter. 🔍"
        tags = "#DominatorGlobal #TechRevolution #AIAssetsX #ViralFramework"
        scenes = [
            f"Vertical pan shot across hyper-digital surfaces depicting {subject} future",
            "Fisheye cental POV through technological gates exploring subject hidden data",
            "Saturated neon transition from darkness to high frequency subject mastery"
        ]

    # توضيب البرومبتات
    prompt_list = []
    for s in scenes:
        prompt_list.append(f"SCENE: {s}. {notes}")
    
    return {
        "hook": hook,
        "script": script,
        "caption": f"{caption}\n\n{tags}",
        "prompts": prompt_list
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/v1/session", methods=["GET"])
def get_session():
    return jsonify({"creator_id": "DOM_" + secrets.token_hex(4).upper()})

@app.route("/v1/build-pack", methods=["POST"])
def build_pack():
    try:
        data = request.json
        res = generate_full_content(data.get("subject", "Tech"), data.get("lang", "en"))
        return jsonify({"success": True, "payload": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
