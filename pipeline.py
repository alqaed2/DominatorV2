from __future__ import annotations

import json
import re
import time
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

from config import settings
from services.trends import get_trending_hashtags


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def run_build_pack(payload: dict) -> dict:
    mode = (payload.get("mode") or "niche").lower()
    platforms = payload.get("platforms") or ["linkedin", "x", "tiktok"]
    language = payload.get("language") or "ar"
    tone = payload.get("tone") or "authority"
    include_visual = bool(payload.get("include_visual", True))

    # 1) Signal: trends + optional url text
    trends = get_trending_hashtags(limit=15)

    input_value = ""
    url_text = ""
    if mode == "url":
        input_value = payload.get("url") or ""
        if input_value:
            url_text = fetch_url_text(input_value)
    else:
        input_value = payload.get("niche") or ""

    context = {
        "mode": mode,
        "niche": input_value if mode == "niche" else "",
        "url": input_value if mode == "url" else "",
        "url_text": url_text[:6000],
        "trends": trends,
        "language": language,
        "tone": tone,
        "platforms": platforms,
    }

    # 2) DNA genes
    genes = extract_genes(context)

    # 3) Generate assets
    assets = generate_assets(context, genes)

    # 4) Visual sovereignty
    visual = {}
    if include_visual:
        v_prompt = generate_visual_prompt(context, genes, assets)
        visual = {
            "prompt": v_prompt,
            "image_url": make_pollinations_url(v_prompt),
        }

    # 5) Dominance scoring
    dominance = dominance_score(context, genes, assets)

    return {
        "mode": mode,
        "input_value": input_value,
        "language": language,
        "platforms": platforms,
        "tone": tone,
        "genes": genes,
        "assets": assets,
        "visual": visual,
        "dominance": dominance,
        "sources": {
            "trends": trends,
            "url": context.get("url"),
        },
    }


def fetch_url_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "AI-DOMINATOR/1.0"})
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "lxml")
        # remove scripts/styles
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return ""


def nebula_models() -> list[str]:
    models = [m.strip() for m in (settings.NEBULA_MODELS or "").split(",") if m.strip()]
    if not models:
        models = [settings.GEMINI_MODEL]
    return models


def call_gemini(prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> str:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        # Hard fallback: deterministic text if key missing
        return ""

    models = nebula_models()
    last_err = None

    for model in models:
        try:
            url = f"{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}"
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            r = requests.post(url, json=body, timeout=settings.MODEL_TIMEOUT_SEC)
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = f"{model} -> {r.status_code}"
                # prompt shrink on rate-limit
                prompt = prompt[: max(1200, int(len(prompt) * 0.7))]
                continue

            r.raise_for_status()
            data = r.json()
            text = _extract_text_from_gemini(data)
            if text.strip():
                return text.strip()
            last_err = f"{model} -> empty"
        except Exception as e:
            last_err = f"{model} -> {e}"

    return "" if last_err is None else ""


def _extract_text_from_gemini(data: dict) -> str:
    try:
        cands = data.get("candidates") or []
        if not cands:
            return ""
        content = cands[0].get("content") or {}
        parts = content.get("parts") or []
        out = []
        for p in parts:
            if "text" in p:
                out.append(p["text"])
        return "\n".join(out)
    except Exception:
        return ""


def extract_genes(context: dict) -> dict:
    prompt = f"""
You are SIC (Strategic Intelligence Core).
Return ONLY strict JSON (no markdown, no commentary).

Task: Extract "success DNA genes" for a content pack.

Inputs:
- language: {context["language"]}
- tone: {context["tone"]}
- mode: {context["mode"]}
- niche: {context.get("niche","")}
- url: {context.get("url","")}
- url_text_excerpt: {context.get("url_text","")[:1200]}
- trends: {context.get("trends",[])}

Return JSON schema:
{{
  "angle": "string",
  "hook_formula": "string",
  "authority_claim": "string",
  "key_points": ["string", ...],
  "emotional_triggers": ["string", ...],
  "cta_style": "string",
  "do_not_do": ["string", ...]
}}
"""
    raw = call_gemini(prompt, temperature=0.4, max_tokens=900)
    genes = _safe_json(raw) or {}
    if not genes:
        # fallback genes
        genes = {
            "angle": "تحويل فكرة مبعثرة إلى قرار عملي خلال دقائق",
            "hook_formula": "سؤال صادم + وعد محدد + دليل سريع",
            "authority_claim": "هذا ليس رأيًا؛ هذه آلية تشغيل قابلة للقياس",
            "key_points": ["الخطأ الشائع", "القاعدة الجديدة", "خطوات التنفيذ", "مقياس النجاح"],
            "emotional_triggers": ["الفضول", "الخوف من التخلف", "الرغبة في السيطرة"],
            "cta_style": "اطلب من القارئ تنفيذ خطوة واحدة الآن",
            "do_not_do": ["حشو", "عموميات", "وعود بلا قياس"],
        }
    return genes


def generate_assets(context: dict, genes: dict) -> dict:
    platforms = context.get("platforms") or ["linkedin", "x", "tiktok"]
    language = context.get("language", "ar")
    tone = context.get("tone", "authority")

    prompt = f"""
You are a cross-platform content reactor.
Return ONLY strict JSON.

Generate assets for platforms: {platforms}
Language: {language}
Tone: {tone}
Trends: {context.get("trends",[])}

Genes:
{json.dumps(genes, ensure_ascii=False)}

If mode=url, incorporate key details from url_text_excerpt:
{context.get("url_text","")[:1200]}

Return JSON schema:
{{
  "linkedin": {{
    "headline": "string",
    "post": "string",
    "hashtags": ["string", ...]
  }},
  "x": {{
    "tweet": "string",
    "thread": ["string", ...]
  }},
  "tiktok": {{
    "hook": "string",
    "script": ["string", ...],
    "shot_list": ["string", ...]
  }}
}}
Only include keys for requested platforms.
"""
    raw = call_gemini(prompt, temperature=0.7, max_tokens=1500)
    assets = _safe_json(raw) or {}

    # Minimal fallback if model returns nothing
    if not assets:
        assets = {}

    # Ensure platform keys exist if requested
    if "linkedin" in platforms and "linkedin" not in assets:
        assets["linkedin"] = {
            "headline": "كيف تحول الترند إلى سلطة معرفية خلال 15 دقيقة؟",
            "post": "الترند ليس فكرة… الترند إشارة. إذا قرأتها صح، ستصنع محتوى يبدو كأنه صادر من وكالة عالمية.\n\n1) التقط الإشارة\n2) استخرج الجينات\n3) صُغ الزاوية\n4) سلّم قيمة قابلة للتنفيذ\n\nإذا تريد، اكتب نيشك وسأبني لك Pack جاهز.",
            "hashtags": context.get("trends", [])[:8],
        }

    if "x" in platforms and "x" not in assets:
        assets["x"] = {
            "tweet": "الترند ليس محتوى… الترند “إشارة قرار”. اقرأها صح واصنع سلطة معرفية في دقائق.",
            "thread": [
                "١) التقط الإشارة من السوق لا من رأسك",
                "٢) استخرج DNA النجاح (hook/زاوية/CTA)",
                "٣) اكتب كأنك تملك الدليل لا الرأي",
                "٤) سلّم خطوة واحدة قابلة للتنفيذ",
            ],
        }

    if "tiktok" in platforms and "tiktok" not in assets:
        assets["tiktok"] = {
            "hook": "إذا كنت تكتب محتوى عشوائي… فأنت تلعب ضد خوارزميات العالم.",
            "script": [
                "اليوم سأريك كيف نحول الترند إلى خطة.",
                "خطوة 1: نلتقط الإشارة.",
                "خطوة 2: نستخرج الجينات.",
                "خطوة 3: نصنع زاوية سيادية.",
                "اختم: اطلب Pack جاهز باسم نيشك.",
            ],
            "shot_list": ["لقطة قريبة مع hook", "كتابة على شاشة", "3 خطوات سريعة", "CTA نهائي"],
        }

    return assets


def generate_visual_prompt(context: dict, genes: dict, assets: dict) -> str:
    # Build a visual prompt aligned with content
    anchor = genes.get("angle", "")
    prompt = f"""
Create a single cinematic, ultra-realistic professional photograph prompt.
Style: advertising agency quality, realistic lighting, shallow depth of field, 35mm photo look.
Must match this angle: {anchor}
Language context: {context.get("language","ar")}
No text in image, no logos.

Return ONLY the prompt sentence.
"""
    out = call_gemini(prompt, temperature=0.8, max_tokens=120)
    out = (out or "").strip()
    if not out:
        out = "Ultra-realistic cinematic photo of a confident strategist working on a glowing dashboard at night, modern minimal office, soft rim light, shallow depth of field, 35mm professional photography, high detail, no text, no logos."
    return out


def make_pollinations_url(prompt: str) -> str:
    # Pollinations free image endpoint (URL-based)
    return f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1024&height=1024&seed=7&nologo=true"


def dominance_score(context: dict, genes: dict, assets: dict) -> dict:
    trends = [t.lower() for t in context.get("trends", []) if isinstance(t, str)]
    score = 50
    reasons = []

    # Heuristic: strong hook?
    hook = genes.get("hook_formula", "") or ""
    if len(hook) >= 12:
        score += 10
        reasons.append("Hook واضح ومهيكل (صيغة جذب قوية).")

    # Heuristic: specificity
    key_points = genes.get("key_points") or []
    if isinstance(key_points, list) and len(key_points) >= 4:
        score += 10
        reasons.append("نقاط محورية متعددة (محتوى قابل للتقسيم وإعادة الاستخدام).")

    # Trend fit: hashtags usage
    used = 0
    for p in ("linkedin", "x", "tiktok"):
        block = assets.get(p) or {}
        blob = json.dumps(block, ensure_ascii=False).lower()
        for t in trends[:8]:
            if t and t in blob:
                used += 1
                break
    if used >= 1:
        score += 10
        reasons.append("مواءمة مع ترندات/هاشتاقات حالية (Trend-fit موجود).")

    # CTA presence
    cta = (genes.get("cta_style", "") or "").strip()
    if len(cta) > 8:
        score += 8
        reasons.append("CTA محدد (يقود لفعل واضح).")

    # Penalty: too generic
    generic_words = ["مهم", "جداً", "لازم", "ضروري", "أفضل", "مميز"]
    blob_all = json.dumps(assets, ensure_ascii=False)
    if sum(1 for w in generic_words if w in blob_all) >= 4:
        score -= 6
        reasons.append("يوجد بعض العموميات؛ يمكن زيادة الدقة والأرقام.")

    score = max(0, min(100, score))

    recommendation = "publish" if score >= 75 else ("revise" if score >= 55 else "regenerate")

    if not reasons:
        reasons = ["مقبول مبدئيًا، لكن يحتاج مزيدًا من التمايز."]

    return {"score": score, "reasons": reasons[:3], "recommendation": recommendation}


def _safe_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    # attempt to locate JSON object
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except Exception:
        return None
