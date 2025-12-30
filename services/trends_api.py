# services/trends_api.py
from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.trends_provider import get_trends_provider

trends_bp = Blueprint("trends_bp", __name__)

@trends_bp.get("/v1/trending-hashtags")
def trending_hashtags():
    """
    GET /v1/trending-hashtags?creator_id=...&limit=12&lang=en&topic=...
    Response:
      { "hashtags":[...], "source":"...", "updated_at":"..." }
    """
    creator_id = (request.args.get("creator_id") or "").strip()
    if not creator_id:
        return jsonify({"error": "creator_id مطلوب"}), 400

    # optional knobs (UI can ignore these; defaults still work)
    limit_raw = (request.args.get("limit") or "12").strip()
    try:
        limit = max(1, min(30, int(limit_raw)))
    except Exception:
        limit = 12

    lang = (request.args.get("lang") or "en").strip().lower()
    topic = (request.args.get("topic") or "").strip() or None

    provider = get_trends_provider()
    res = provider.get_hashtags(creator_id=creator_id, limit=limit, lang=lang, topic=topic)

    return jsonify({
        "hashtags": res.hashtags,
        "source": res.source,
        "updated_at": res.updated_at,
    })
