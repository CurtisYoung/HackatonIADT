from __future__ import annotations

import os
import json
from typing import Optional, Protocol
from dataclasses import dataclass, field

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisLike(Protocol):
    def get(self, key: str) -> Optional[str]: ...
    def set(self, key: str, value: str) -> bool: ...


@dataclass
class MemoryStore:
    _data: dict = field(default_factory=dict)

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> bool:
        self._data[key] = value
        return True


class InMemoryRedis:
    def __init__(self):
        self._data: dict = {}

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> bool:
        self._data[key] = value
        return True

    def ping(self) -> bool:
        return True


_memory_redis = InMemoryRedis()


def get_redis_client() -> RedisLike:
    if not REDIS_AVAILABLE:
        return _memory_redis

    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    redis_url = os.environ.get("REDIS_URL")

    if not redis_host or redis_host.lower() == "false" or redis_host.lower() == "none":
        return _memory_redis

    try:
        if redis_url:
            return redis.from_url(redis_url, decode_responses=True)
        return redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
    except Exception:
        return _memory_redis