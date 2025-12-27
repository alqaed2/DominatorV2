import json
import logging
from config import settings


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    h = logging.StreamHandler()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s")
    h.setFormatter(fmt)
    logger.addHandler(h)
    logger.propagate = False
    return logger


def safe_json(data) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return "{}"
