from __future__ import annotations

import os
import redis

def get_redis_client() -> redis.Redis:
    """Cria e retorna um cliente Redis."""
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    return redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
