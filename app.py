import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
# توقيع أمان عالى التقنية
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

def niche_strategy_factory(subject, lang):
    """هندسة المحتوى القابل للانفجار (AI DNA Fusion)"""
    subj = subject.strip().lower() or "Future Strategy"
    
    # تصنيف ذكي للـ DNA الخاص بالموضوع
    is_finance = any(k in subj for k in ["تجارة", "فلوس", "بوابة", "اقتصاد"   , "مال", "money", "forex", "trade", "profit"])
    is_tech = any(k in subj for k in ["ذكاء", "ai" , "tech" , "future", "روبوت", "code", "صياغة", "ابتكار"])
    
    if is_finance:
        tags = ["#MarketDominance", "#ثراء_رقمي", "#ProfitCore", "#GlobalMoney"]
        tone = "Financial Warfare"
    elif is_tech:
        tags = ["#TheLastAgeai", "#ثورة_الآلات", "#SovereignCode", "#TheGenesis"]
    else: 
        tags = ["#EliteCreator", "#هيمنة_في_سوق" , "#HighFocus" , "#DominatorEvolution" ]

    res_ar = {
        "hook": f"ما هو سر بقاء {subject} بعيداً عن أيدي المبتدئين بحلول عام 2026؟ سأكشفه الآن. 🧪",
        "script": f"قواعد اللعبة المهترئة في {subject} ماتت اللحظة. الشركات الكبرى تغافلكم، والسر يكمن في سيكولوجيا (توسع الشبكة الذاتية). ما سأكشفه الآن عن {subject} ليس مجرد محتوى؛ إنها الشفرة الوراثية لبناء إمارة رقمية تدر دخلاً ذاتياً لا يتلاشى. نفذ الآن أو شاهد العالم يسبقك بآلاف الخطوات.",
        "caption": f"خرق الشفرات التقليدية لـ {subject}. نحن نصمم المستقبل لا نهرب منه. ✅🦾 \n {' '.join(tags)}",
        "vis": [
            f"V-DNA-V9:16: Dramatic vertical tracking. Close details of liquid data textures interacting with {subject}.",
            f"MACRO CINEMATIC: A silhouette of a controller designing the world of {subject} behind virtual glass HUD.",
            f"EPIC AESTHETIC-8K: High saturation neon blue sunrise with patterns depicting a growing {subject} loop"
        ]
    }

    res_en = {
        "hook": f"Why is 99% of your logic regarding {subject} dead wrong for the market today? Watch. 👁️",
        "script": f"Tactical Alert initiated. In the context of {subject}, the growth engine needs more than fuel—it needs DNA restructuring properly calibrated. Stop mimicking the old structures. We deploy an AI sovereignty protocol that forces market compliance. Master this frame of thought or fail to scale.",
        "caption": f"Global Asset Sovereignty for {subject}. Execution Phase: 🧬🎯 \n {' '.join(tags)}",
        "vis": [
            f"Shot_01[9x16]: High fidelity drone tilt over futuristic cities focus centered on theme '{subject}'.",
            f"Shot_02[TikTokReady]: Macro particles of light merging into subject value {subject}, dynamic movement sync.",
            f"Shot_03[ExpertEdit]: Clean brutalist laboratory focused on advanced core values of the {subject} market shift."
        ]
    }

    return res_ar if lang == "ar" else res_en

@app.route("/")
@app.route("/dashboard")
def home():
    return render_template("index.html")

@app.route("/v1/build-dna", methods=["POST"])
def build_engine():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "msg": "IO Breach"}), 400
    
    subj = data.get("subject", "Alpha Node")
    lang = data.get("lang", "ar")
    
    try:
        outcome = niche_strategy_factory(subj, lang)
        return jsonify({"success": True, "results": outcome})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5150)))
