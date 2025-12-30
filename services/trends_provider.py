# services/trends_provider.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Protocol

import requests


@dataclass
class TrendsResult:
    hashtags: List[str]
    source: str
    updated_at: str  # ISO8601


class TrendsProvider(Protocol):
    def get_hashtags(
        self,
        *,
        creator_id: str,
        limit: int = 12,
        lang: str = "en",
        topic: Optional[str] = None,
    ) -> TrendsResult:
        ...


_HASHTAG_RX = re.compile(r"^#\w+", re.UNICODE)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_hashtag(tag: str) -> Optional[str]:
    if tag is None:
        return None
    t = str(tag).strip()
    if not t:
        return None

    # Ensure it starts with '#'
    if not t.startswith("#"):
        t = "#" + t

    # Replace spaces with underscore
    t = re.sub(r"\s+", "_", t)

    # Basic validity
    if not _HASHTAG_RX.match(t):
        # allow Arabic hashtags too: keep # + anything non-space
        if len(t) >= 2 and t.startswith("#") and " " not in t:
            return t
        return None

    return t


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


class ExternalTrendsAPIProvider:
    """
    Plug any external trends provider without changing UI.
    Configure:
      - TRENDS_API_URL  (required)
      - TRENDS_API_KEY  (optional)
      - TRENDS_API_KEY_HEADER (optional, default: Authorization)
      - TRENDS_API_KEY_PREFIX (optional, default: Bearer)
    Expected response JSON:
      { "hashtags": ["#tag1", "#tag2", ...], ... }
    """

    def __init__(self) -> None:
        self.url = os.getenv("TRENDS_API_URL", "").strip()
        self.api_key = os.getenv("TRENDS_API_KEY", "").strip()
        self.api_key_header = os.getenv("TRENDS_API_KEY_HEADER", "Authorization").strip()
        self.api_key_prefix = os.getenv("TRENDS_API_KEY_PREFIX", "Bearer").strip()
        self.timeout_sec = float(os.getenv("TRENDS_API_TIMEOUT", "6").strip() or "6")

        if not self.url:
            raise ValueError("TRENDS_API_URL is not set")

    def get_hashtags(
        self,
        *,
        creator_id: str,
        limit: int = 12,
        lang: str = "en",
        topic: Optional[str] = None,
    ) -> TrendsResult:
        headers = {"Accept": "application/json"}
        if self.api_key:
            if self.api_key_header.lower() == "authorization":
                headers[self.api_key_header] = f"{self.api_key_prefix} {self.api_key}".strip()
            else:
                headers[self.api_key_header] = self.api_key

        payload = {
            "creator_id": creator_id,
            "limit": int(limit),
            "lang": lang,
            "topic": topic or "",
        }

        r = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout_sec)
        r.raise_for_status()
        data = r.json()

        tags = data.get("hashtags") or []
        if not isinstance(tags, list):
            tags = []

        normalized = [t for t in (_normalize_hashtag(x) for x in tags) if t]
        normalized = _dedupe_keep_order(normalized)[: int(limit)]

        return TrendsResult(
            hashtags=normalized,
            source="external",
            updated_at=data.get("updated_at") or _iso_now(),
        )


class StaticFallbackProvider:
    """
    Smart-enough fallback that always returns something usable.
    Uses language-aware buckets + minimal topical hints.
    """

    def get_hashtags(
        self,
        *,
        creator_id: str,
        limit: int = 12,
        lang: str = "en",
        topic: Optional[str] = None,
    ) -> TrendsResult:
        # Baseline tags (safe, evergreen)
        en_base = [
            "#marketing",
            "#digitalmarketing",
            "#contentmarketing",
            "#socialmedia",
            "#branding",
            "#growth",
            "#business",
            "#entrepreneur",
            "#strategy",
            "#productivity",
            "#learn",
            "#tips",
        ]

        ar_base = [
            "#التسويق_الرقمي",
            "#تسويق",
            "#صناعة_المحتوى",
            "#سوشيال_ميديا",
            "#ريادة_الأعمال",
            "#مشروع",
            "#تطوير_الذات",
            "#نصائح",
            "#تعلم",
            "#استراتيجية",
            "#نجاح",
            "#بيزنس",
        ]

        buckets = {
            "en": en_base,
            "ar": ar_base,
            "es": ["#marketingdigital", "#emprendimiento", "#negocios", "#consejos", "#aprende"],
            "fr": ["#marketingdigital", "#entrepreneur", "#business", "#conseils", "#apprendre"],
            "de": ["#marketing", "#unternehmen", "#business", "#tipps", "#lernen"],
            "pt": ["#marketingdigital", "#empreendedorismo", "#negocios", "#dicas", "#aprenda"],
            "tr": ["#dijitalpazarlama", "#girişimcilik", "#iş", "#ipuçları", "#öğren"],
            "ru": ["#маркетинг", "#бизнес", "#советы", "#обучение", "#стратегия"],
            "id": ["#digitalmarketing", "#bisnis", "#tips", "#belajar", "#strategi"],
        }

        base = buckets.get(lang, en_base).copy()

        # Minimal topical hinting
        t = (topic or "").lower().strip()
        if t:
            if any(k in t for k in ["seo", "search"]):
                base = (["#seo", "#searchengineoptimization", "#google"] + base)
            if any(k in t for k in ["ads", "paid", "ppc"]):
                base = (["#ads", "#ppc", "#facebookads", "#googleads"] + base)
            if any(k in t for k in ["tiktok", "shorts", "reels"]):
                base = (["#tiktokmarketing", "#shortformvideo", "#reels"] + base)
            if any(k in t for k in ["content", "copy", "script"]):
                base = (["#copywriting", "#contentcreator", "#storytelling"] + base)

        # Normalize + limit
        normalized = [t for t in (_normalize_hashtag(x) for x in base) if t]
        normalized = _dedupe_keep_order(normalized)[: int(limit)]

        return TrendsResult(
            hashtags=normalized,
            source="static_fallback",
            updated_at=_iso_now(),
        )


class SmartMixerProvider:
    """
    Tries external first; if it fails, falls back.
    If external returns few tags, it tops up from fallback.
    """

    def __init__(self, primary: TrendsProvider, fallback: TrendsProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def get_hashtags(
        self,
        *,
        creator_id: str,
        limit: int = 12,
        lang: str = "en",
        topic: Optional[str] = None,
    ) -> TrendsResult:
        limit = int(limit)

        primary_res: Optional[TrendsResult] = None
        try:
            primary_res = self.primary.get_hashtags(
                creator_id=creator_id, limit=limit, lang=lang, topic=topic
            )
        except Exception:
            primary_res = None

        fb_res = self.fallback.get_hashtags(creator_id=creator_id, limit=limit, lang=lang, topic=topic)

        if not primary_res:
            return fb_res

        merged = _dedupe_keep_order((primary_res.hashtags or []) + (fb_res.hashtags or []))[:limit]
        return TrendsResult(
            hashtags=merged,
            source=f"{primary_res.source}+{fb_res.source}",
            updated_at=primary_res.updated_at or _iso_now(),
        )


def get_trends_provider() -> TrendsProvider:
    """
    Switch provider without touching UI or route:
      - TRENDS_PROVIDER=external   -> external + fallback mixer
      - TRENDS_PROVIDER=static     -> fallback only
    """
    choice = os.getenv("TRENDS_PROVIDER", "static").strip().lower()

    fallback = StaticFallbackProvider()

    if choice == "external":
        # external + fallback
        primary = ExternalTrendsAPIProvider()
        return SmartMixerProvider(primary=primary, fallback=fallback)

    # default: static fallback only
    return fallback
