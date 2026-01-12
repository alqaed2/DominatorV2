from __future__ import annotations

# Compatibility shim:
# Existing code imports: from services.trends import get_trending_hashtags
# But repo currently has trends_provider.py / trends_api.py, not trends.py.
# This file bridges that gap safely without breaking boot.

def _mock_trends(limit: int = 15) -> list[str]:
    base = [
        "#الذكاء_الاصطناعي",
        "#تسويق",
        "#ريادة_الأعمال",
        "#إنتاجية",
        "#LinkedIn",
        "#X",
        "#TikTok",
        "#صناعة_المحتوى",
        "#مبيعات",
        "#إدارة",
        "#تطوير_الذات",
        "#استراتيجية",
        "#تحليل_بيانات",
        "#برمجة",
        "#مستقبل",
    ]
    return base[:limit]


def _load_provider_func():
    # Try trends_provider.py
    try:
        from . import trends_provider as tp  # type: ignore
        for name in ("get_trending_hashtags", "get_trends", "get_hashtags", "fetch_trends"):
            fn = getattr(tp, name, None)
            if callable(fn):
                return fn
    except Exception:
        pass

    # Try trends_api.py
    try:
        from . import trends_api as ta  # type: ignore
        for name in ("get_trending_hashtags", "get_trends", "get_hashtags", "fetch_trends"):
            fn = getattr(ta, name, None)
            if callable(fn):
                return fn
    except Exception:
        pass

    return None


_PROVIDER_FN = _load_provider_func()


def get_trending_hashtags(limit: int = 15) -> list[str]:
    """
    Public API expected by pipeline/app.
    Always returns a safe list (never crashes server boot).
    """
    try:
        if _PROVIDER_FN:
            result = _PROVIDER_FN(limit=limit)  # supports keyword if implemented
            if isinstance(result, list):
                clean = [str(x).strip() for x in result if str(x).strip()]
                if clean:
                    return clean[:limit]
    except TypeError:
        # Provider may accept positional only: fn(limit)
        try:
            result = _PROVIDER_FN(limit) if _PROVIDER_FN else None
            if isinstance(result, list):
                clean = [str(x).strip() for x in result if str(x).strip()]
                if clean:
                    return clean[:limit]
        except Exception:
            pass
    except Exception:
        pass

    return _mock_trends(limit)
