import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def intelligent_niche_fusion(subject, lang):
    """محرك التحليل العالي الدقة (DNA Extraction Logic)"""
    s = str(subject).strip() if subject else "General Success"
    
    # تصنيف ذكي للمجال لمنع التداخلات البرمجية
    # الكلمات المفتاحية تم تنظيفها من أحرف الهروب (Escape Characters)
    k_biz = ["تجارة", "بزنس", "اقتصاد", "مال", "success", "money", "ثروة"]
    is_biz = any(k in s.lower() for k in k_biz)
    
    tags = ["#Dominance2026", "#AlphaNiche", "#FutureReady"]
    
    if lang == "ar":
        hook = f"السر خلف نجاح {s} ليس في المجهود، بل في 'الخوارزمية الصامتة' التي تتجاهلها! 🔍"
        script = (f"كل هؤلاء يدعون أن محتوى {s} سهل التحقيق.. هم يكذبون عليك ليس لحماية المال، بل لحماية السيطرة. "
                  f"بناء الـ DNA الخاص بصناعة محتواك هنا يتطلب ذكاءً إجرائيًا يتخطى المنافسين بعقود.")
        caption = f"خطة الهجوم في نيش {s}. السيطرة أو الجمود.. الخيار لك. ✅⚡\n {' '.join(tags)}"
    else:
        hook = f"Your competition worships {s} volume, while we worship {s} architecture. Watch. 📊"
        script = (f"In 2026, mediocrity is terminal. If you scale {s} without technical DNA integration, you fail. "
                  f"We restructured this protocol for absolute niche conversion. Execute properly.")
        caption = f"The {s} Domination Manual. Phase One. 🧬🪐\n {' '.join(tags)}"

    visuals = [
        {"id": "V1", "desc": f"POV 9-16 Vertical: 8K Close-up showing {s} elements glowing in cyberpunk void."},
        {"id": "V2", "desc": f"DRAMATIC TILT: Visualizing the massive structural growth of {s} markets with bokeh."},
        {"id": "V3", "desc": f"CENTRIC VIEW: Minimalist cinematic shot centering {s} essence for loop retention."}
    ]

    return {"hook": hook, "script": script, "caption": caption, "visuals": visuals}

@app.route("/")
@app.route("/dashboard")
def index():
    return render_template("index.html")

@app.route("/v1/build-dna", methods=["POST"])
def build():
    try:
        data = request.get_json(silent=True)
        if not data or 'subject' not in data:
            return jsonify({"success": False, "msg": "Subject Void"}), 400
        
        bundle = intelligent_niche_fusion(data['subject'], data.get('lang', 'ar'))
        return jsonify({"success": True, "results": bundle})
    except Exception as e:
        return jsonify({"success": False, "msg": "Infiltration Detected"}), 500

if __name__ == "__main__":
    # تشغيل متوافق مع كافة المنصات السحابية
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
