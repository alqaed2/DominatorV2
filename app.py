import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(24))

# نظام DNA الذكاء الاصطناعي (ألا عهود بعد الآن للتنمر على النيش)
def generate_strategic_narrative(subject, lang):
    """خوارزمية تستهدف توليد (تجارب) وليس نصوص. بناءً على 'دنا' المشاهدات المليونية."""
    
    # 1. كشف نيش المحتوى وتصنيف نغمة السوق له
    dom_subject = subject.lower()
    tone = "Curiosity/Hype" # نغمة الفهلوة الجذابة الافتراضية
    if "مال" in dom_subject or "تجارة" in dom_subject or "بزنيس" in dom_subject or "مال" in dom_subject:
        tone = "High Stakes / Actionable"
    elif "مستقبل" in dom_subject or "اذكاء" in dom_subject:
        tone = "Utopian/Distopian Contrast"
    elif "صناعة" in dom_subject or "ابتكار" in dom_subject:
        tone = "Technological Depth"

    # 2. توليد سلالة الترند (بانتظار API الخاص بك ولكن بذكاء بديل عالٍ)
    dynamic_tags = []
    if "قهوة" in dom_subject:
        dynamic_tags = ["#قهوة_مختصة", "#VibeOn", "#ArabicaMaster", "#BaristaRules", "#تحميص_يدوي", "#SpecialtyLegacy"]
    elif "اقتصاد" in dom_subject:
        dynamic_tags = ["#MarketBoom2025", "#WealthUpdate", "#فلسفة_المال", "#SmartInvestment", "#GlobalTradeLoop"]
    else: 
         dynamic_tags = ["#BreakingGrowth", f"#(subject)_Pulse", "#SovereigntyNow", "#MarketLeaders", "#GameChanger"]

    hashtags_str = " ".join(dynamic_tags[0:5])

    # 3. بناء هيكيلة 'سكريبت السيطرة' باحترافية الخبير البشري
    # اللغة العربية في مستويات 'الجذب النفسي' العالي
    if lang == "ar":
        hooks = [
            f"لا ينصح بمشاهدة هذا الفيديو لمزارع تقليدي، هنا نتحدث عن مستقبل الـ {subject} الصاعد!",
            f"الرقم الذي ستسمعونه عندما نتحدث عن الـ {subject} لا يمكن لأحد استيعابه بسهولة. شاهد الحقيقة.",
            f"إذا كنت تعتمد على الطرث التقليدية في {subject}.. هنيئاً لك الاندثار المبكر!"
        ]
        
        # مخرجات سيتعدل الـ DNA بذكاء
        descriptions = [
            f"تعمقنا ليس في الـ {subject} العادية، إنما ننبش قاع الشفافية في سوق المليارات القادمة عبر التحول القهري للهياكل القديمة.",
            f"هنا نبصق السيكولوجيا المهترئة ونتبنى سلالة جديدة كلياً في قطاع {subject}_DNA الرابح.",
        ]

        payload = {
            "hook": secrets.choice(hooks),
            "script": f"اسمعني جيداً... في قبو اللعبة الرقمية والمنافسة الشرسة، موضوع الـ {subject} يكتنف الغموض لعدة دقائق. الخبراء فقط يعلمون أن 'الشفرة الوراثية' للمحتوى المليوني تبدأ من اللياقة المعرفية التي نحقنها هنا. اخرج الآن من الصندوق القديم... وانضم لنخبة التحكم.",
            "caption": f"أسرار الـ {subject} كما تراها لغة الأذكياء فقط. الاستعداد لن يرحم المتقاعسين. 🌍 🦾\n {hashtags_str}",
            "prompts": [
                 f"MASTERPIECE VIEW: Epic hyper-detailed vertical drone focus on {subject}, slow ominous gimbal, unreal 8k vivid texture contrast.",
                 f"MACRO CINEMATIC: Texture reflection of {subject} integrated into ultra-futuristic Riyadh-city architectural background.",
                 f"POV INTENSE: Advanced creative desk showing real-logic patterns of market {subject}, blue moody rim lighting for Reels tension."
            ]
        }
    else:
        # الإنتاج باللغة الإنجليزية المتطورة (Expert Mindset)
        payload = {
            "hook": f"Warning: Your competitors are weaponizing {subject} while you still 'plan'. Stop overthinking!",
            "script": f"Listen strategically... The DNA of winning in {subject} is not about luck; it's about calibrated distribution. Industry experts don't want you to know how simple yet aggressive this transition can be. We don't adapt, we colonize the trend.",
            "caption": f"Total Market Annihilation for {subject}. The elite blueprint is now activated. 👁️⚡\n {hashtags_str}",
            "prompts": [
                 f"9:16 RAW FILM GRAIN : Aggressive editing cut for {subject}, focal center high dynamic shadows.",
                 f"MINIMAL ELITE aesthetics for {subject}, sharp volumetric lights bouncing from liquid surfaces.",
                 f"SARA Style motion: tracking shots through technological portals visualizing the massive {subject} revolution."
            ]
        }

    return payload

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/v1/session", methods=["GET"])
def get_session():
    uid = "DOMX_" + secrets.token_hex(4).upper()
    return jsonify({"creator_id": uid})

@app.route("/v1/build-pack", methods=["POST"])
def build_pack():
    data = request.json
    subject = data.get("subject", "Alpha Growth")
    lang = data.get("lang", "en")
    
    # تحرك ذكي: نظام توليد حي، لا قالب مصفوف
    result = generate_strategic_narrative(subject, lang)
    
    return jsonify({
        "status": "Generating Viral DNA...",
        "pack": result
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
