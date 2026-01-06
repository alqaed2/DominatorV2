import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def elite_viral_architecture(niche, lang):
    """محرك فك الشفرة للموضوع المختصر وحساب نغمة الترند اللحظي"""
    n = niche.strip() if niche else "Alpha Project"
    
    # محرك الهاشتاجات التلقائية الذكية المسلح ببيانات القطاع
    hash_pool = {
        "biz": ["#ثورة_الأعمال", "#MindsetMagic", "#RiyadhBusiness", "#تداول_التركيز"],
        "tech": ["#AiDNA2026", "#مستقبل_النماذج", "#SovereignCode", "#TechTrends"],
        "life": ["#LuxuryMind", "#SaudiExperience", "#VlogLife", "#SpecialtyVibe"]
    }
    
    # تحديد النيش ديناميكياً
    target_key = "biz" if any(x in n.lower() for x in ["مشاركة", "عمارة", "اقتصاد" "money"]) else "tech"
    active_hashes = " ".join(hash_pool.get(target_key, hash_pool["life"]))

    if lang == "ar":
        hook = f"لماذا الجميع يراقب {n} بصمت وهذ المرة؟ الأمر لم يعد سراً! 👁️"
        caption = f"خطة الهيمنة المتسلسلة لـ {n}. بناء أنظمتنا يبدأ بكلمة 'إلغاء' للمقاعد القديمة. \n\n {active_hashes}"
        script = f"استمع جيداً، نجاح {n} المحتمل يتطلب تفاعل الجزيئات السينمائية مع الجمهور الصعب.. نحن في 2026 والجمهور لن يقبل إلا بمعدن القيمة الوفير."
    else:
        hook = f"The {n} structure is resetting... Why is now the ultimate entry window? 🗺️"
        caption = f"The Complete Mastery Manual for {n}. We stop reacting and start dominating the niche loop. \n\n {active_hashes}"
        script = f"Operational protocol Alpha - Target: {n}. Focus on kinetic movement and focal visual gravity. Results guaranteed by 15yrs experience DNA."

    vis = [
        f"CLOSE-UP POV (TIKTOK 9:16): Heavy texture shot of {n} in 8K cinematic grain, center-focused.",
        f"TILT-SHIFT MOTION: A panoramic visual depicting the rapid growth wave of {n} in futuristic tones.",
        f"AESTHETIC LOOP: A single artistic object revolving about {n} reflecting purple neon lights."
    ]

    return {"hook": hook, "script": script, "caption": caption, "visuals": vis}

@app.route("/")
@app.route("/dashboard")
def dashboard():
    return render_template("index.html")

@app.route("/v1/build-dna", methods=["POST"])
def build_engine():
    try:
        data = request.get_json()
        niche_input = data.get('subject', 'Tech Evolution')
        lang = data.get('lang', 'ar')
        result_bundle = elite_viral_architecture(niche_input, lang)
        return jsonify({"success": True, "bundle": result_bundle})
    except:
        return jsonify({"success": False, "msg": "Nucleous Server Failure"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
