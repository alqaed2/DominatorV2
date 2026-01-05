import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(24))

# قاموس المعرفة الاستخباراتي DNA Knowledge base
def analyze_niche_dna(subject, lang):
    sub = subject.lower()
    # نظام ترندات افتراضي ذكي "Synthetic Trends" يتغير حسب النيش
    if any(k in sub for k in ["تجارة", "بزنيس", "فلوس", "اقتصاد", "coffee", "business"]):
        niche_tags = ("ar", ["#قهوة_مختصة_السعودية", "#استثمار_رابح", "#بزنس_تيك", "#تيكتاك_بزنس"]) if lang=="ar" else ("en", ["#ArabicaProfits", "#NicheEmpire", "#BizLogic", "#TikTokGrowth"])
    elif any(k in sub for k in ["ذكاء", "ai", "تقنية", "tech"]):
        niche_tags = ("ar", ["#ذكاء_اصطناعي", "#تكنولوجيا_المستقبل", "#بناء_الأنظمة", "#هندسة_الأرباح"]) if lang=="ar" else ("en", ["#GlobalAI", "#TechInnovation", "#FutureStack", "#AutomationRules"]) 
    else:
        niche_tags = (lang, ["#DOMv2", "#GameChanger", "#NextLevel", "#SovereigntyNow"])

    if lang == "ar":
        payload = {
            "hook": f"ما ستسمعة عن سيكولوجية {sub} سيصيب منتقديك بذهول حاد... استمع بعمق 🌋",
            "script": f"قواعد اللعبة المهترئة في {sub} انتهت اليوم. الخبراء الذين تفادوك بـ 15 عام خبرة يستثمرون الآن في الهوية الرقمية المترابطة. نحن ننبش في डीएनए النجاح، لنبني نظاماً يتوسع بمفرده. التفت لكل تفصيل هنا... لأن القفزة تبدأ من قاع المعرفة.",
            "caption": f"الحسابات الفلكية لحقبة {sub} الجديدة. ابق مهيمناً ولا تكن تابعاً. 🧠⚡ \n  {' '.join(niche_tags[1])}",
            "visuals": [
                f"CINEMATIC V9:16: High-detail aesthetic shot of core {sub} elements, anamorphic lens flares, center framing.",
                "VERTICAL DRONE SCAN: futuristic neon surroundings depicting rapid growth transitions.",
                "CYBER VLOG MOTION: Subject focused on intense data visualization with Moody aesthetic lighting."
            ]
        }
    else:
        payload = {
            "hook": f"Is {sub} honestly a gamble? Or are you just lacking the Dominator Blueprint? 🧬",
            "script": f"Industry veterans won't reveal the true catalyst behind {sub} success. It's not about saturation; it's about calibrated distribution. What 15 years taught us is built into this workflow. Stop thinking—start commanding your niche architecture today.",
            "caption": f"Global Sovereignty Protocol for {sub}. Phase 1 Activated. 🌍🦾 \n {' '.join(niche_tags[1])}",
            "visuals": [
                f"9x16 VERTICAL PRO-GRADE: Close focus on {sub} mastery, cinematic grading, extreme sharpness.",
                "MOTION GRAPH 4K: Dark atmospheric transition effects visualizing the core of subject dominance.",
                "VEO3 CINEMA: Tracking masterclasses lighting style, center weighted, minimal elements focus."
            ]
        }
    return payload

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/v1/session", methods=["GET"])
def get_session():
    uid = "DOM-MVP-" + secrets.token_hex(4).upper()
    return jsonify({"creator_id": uid})

@app.route("/v1/build-pack", methods=["POST"])
def build_pack():
    try:
        data = request.json
        subject = data.get("subject", "Strategy Execution")
        lang = data.get("lang", "en")
        raw_out = analyze_niche_dna(subject, lang)
        return jsonify({"pack": raw_out})
    except:
        return jsonify({"error": "System Crash Core-709"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
