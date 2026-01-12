from __future__ import annotations

from redis import Redis
from rq import Queue
from config import settings


def get_redis() -> Redis | None:
    if not settings.REDIS_URL:
        return None
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_queue() -> Queue | None:
    r = get_redis()
    if not r:
        return None
    return Queue(name=settings.QUEUE_NAME, connection=r, default_timeout=settings.MODEL_TIMEOUT_SEC * 4)
