from __future__ import annotations

from rq import Worker, Connection

from config import settings
from rq_queue import get_redis  # ✅ renamed module (avoid stdlib queue collision)

# Ensure the task function is importable for RQ
import tasks  # noqa: F401


def main():
    redis_conn = get_redis()
    if not redis_conn:
        raise RuntimeError("REDIS_URL is not set. Worker cannot start.")

    with Connection(redis_conn):
        w = Worker([settings.QUEUE_NAME])
        w.work(with_scheduler=True)


if __name__ == "__main__":
    main()
