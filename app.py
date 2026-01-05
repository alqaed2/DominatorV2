import os
import secrets
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def intelligent_niche_fusion(subject, lang):
    """محرك التحليل العالي الدقة (DNA Extraction Logic)"""
    s = subject.strip()
    # تصنيف ذكي للمجال لضمان عدم النسخ البارد
    is_biz = any(k in s.lower() for k in ["تجارة", "بزنس", "اقتصاد\", "مال", "success", "money"])
    
    tags = ["#Dominance2026", "#AlphaNiche", "#FutureReady"]
    
    if lang == "ar":
        hook = f"السر خلف نجاح {s} ليس في المجهود، بل في 'الخوارزمية الصامتة' التي تتجاهلها! 🔍"
        script = (f"كل هؤلاء يدعون أن {s} سهلة.. هم يكذبون عليك ليس لحماية المال، بل لحماية السيطرة. "
                  f"بناء الـ DNA الخاص بمشروعك هنا يتطلب ذكاءً إجرائيًا يتخطى المنافسين بـ 10 أعوام. اسمع الشفيرة للأخر.")
        caption = f"خطة الهجوم في نيش {s}. السيطرة أو الجمود.. الخيار لك. ✅⚡\n  {' '.join(tags)}"
    else:
        hook = f"Your competition worships {s} volume, we worship {s} architecture. Watch the drift. 📊"
        script = (f"In 2026, mediocrity is terminal. If you scale {s} without technical DNA integration, you are building on sand. "
                  f"We restructured this protocol for absolute niche conversion. Execute properly or perish slowly.")
        caption = f"The {s} Domination Manual. Phase One. 🧬🪐\n {' '.join(tags)}"

    visuals = [
      {"id": "V1", "desc": f"POV 9:16 Vertical: 8K Close-up showing {s} elements glowing in dark cyberpunk void."},
      {"id": "V2", "desc": f"DRAMATIC TILT: Visualizing the massive structural growth of {s} markets with kinetic blur."},
      {"id": "V3", "desc": f"CENTRIC VIEW: Minimalist but heavy cinematic shot centering {s} essence for loop retention."}
    ]

    return {"hook": hook, "script": script, "caption": caption, "visuals": visuals}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/v1/build-dna", methods=["POST"])
def build():
    try:
        data = request.json
        if not data or 'subject' not in data:
            return jsonify({"success": False, "msg": "Target Subject Null"}), 400
        
        bundle = intelligent_niche_fusion(data['subject'], data.get('lang', 'ar'))
        return jsonify({"success": True, "results": bundle})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
