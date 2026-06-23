from __future__ import annotations

import json
import os
from typing import Any

REDIS_URL = os.getenv("REDIS_URL", "").strip()
DEFAULT_CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

_redis_client = None


def redis_enabled() -> bool:
    return bool(REDIS_URL)


def get_redis_client():
    global _redis_client
    if not REDIS_URL:
        return None
    if _redis_client is None:
        import redis

        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def cache_get_json(key: str) -> Any | None:
    client = get_redis_client()
    if not client:
        return None
    try:
        raw = client.get(key)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int | None = None) -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        client.setex(key, ttl_seconds or DEFAULT_CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False))
        return True
    except Exception:
        return False


def cache_delete(key: str) -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        client.delete(key)
        return True
    except Exception:
        return False


def check_redis() -> dict:
    if not REDIS_URL:
        return {"enabled": False, "status": "disabled"}
    try:
        client = get_redis_client()
        client.ping()
        return {"enabled": True, "status": "ok"}
    except Exception as exc:
        return {"enabled": True, "status": "error", "detail": str(exc)}
