"""
TikTok integration layer (future):
- Manual mode doesn't need this.
- Read-only / Full mode can be implemented here using official APIs.

In MVP we keep it as a clean boundary to avoid coupling.
"""

from __future__ import annotations
from typing import Any


class TikTokClient:
    def __init__(self, client_key: str | None, client_secret: str | None):
        self.client_key = client_key
        self.client_secret = client_secret

    def is_configured(self) -> bool:
        return bool(self.client_key and self.client_secret)

    def post_video(self, access_token: str, video_url: str, caption: str) -> dict[str, Any]:
        raise NotImplementedError("Full Mode not enabled in MVP")

    def fetch_public_metrics(self, video_url: str) -> dict[str, Any]:
        raise NotImplementedError("Use manual submission in MVP")
