from __future__ import annotations

from threading import Lock
from typing import Any, Protocol

from cachetools import TTLCache

from app.config import Settings


class EvaluationCache(Protocol):
    def get_evaluation(self, flag_key: str, user_id: str) -> dict[str, Any] | None: ...

    def set_evaluation(
        self, flag_key: str, user_id: str, enabled: bool, source: str
    ) -> None: ...

    def invalidate_flag(self, flag_key: str) -> None: ...

    def ping(self) -> bool: ...

    def clear(self) -> None: ...


class MemoryEvaluationCache:
    """Process-local TTL cache. Fine for single-instance / tests."""

    def __init__(self, settings: Settings) -> None:
        self._lock = Lock()
        self._cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=settings.cache_maxsize,
            ttl=settings.cache_ttl_seconds,
        )

    @staticmethod
    def _eval_key(flag_key: str, user_id: str) -> str:
        return f"eval:{flag_key}:{user_id}"

    def get_evaluation(self, flag_key: str, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._cache.get(self._eval_key(flag_key, user_id))
            return dict(value) if value is not None else None

    def set_evaluation(
        self, flag_key: str, user_id: str, enabled: bool, source: str
    ) -> None:
        with self._lock:
            self._cache[self._eval_key(flag_key, user_id)] = {
                "enabled": enabled,
                "source": source,
            }

    def invalidate_flag(self, flag_key: str) -> None:
        prefix = f"eval:{flag_key}:"
        with self._lock:
            keys = [key for key in self._cache if key.startswith(prefix)]
            for key in keys:
                del self._cache[key]

    def ping(self) -> bool:
        return True

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class RedisEvaluationCache:
    """Shared TTL cache for multi-instance deployments."""

    def __init__(self, settings: Settings) -> None:
        import redis

        self._ttl = settings.cache_ttl_seconds
        self._client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )

    @staticmethod
    def _eval_key(flag_key: str, user_id: str) -> str:
        return f"ff:eval:{flag_key}:{user_id}"

    def get_evaluation(self, flag_key: str, user_id: str) -> dict[str, Any] | None:
        raw = self._client.hgetall(self._eval_key(flag_key, user_id))
        if not raw:
            return None
        return {
            "enabled": raw["enabled"] == "1",
            "source": raw["source"],
        }

    def set_evaluation(
        self, flag_key: str, user_id: str, enabled: bool, source: str
    ) -> None:
        key = self._eval_key(flag_key, user_id)
        pipe = self._client.pipeline()
        pipe.hset(
            key,
            mapping={"enabled": "1" if enabled else "0", "source": source},
        )
        pipe.expire(key, self._ttl)
        pipe.execute()

    def invalidate_flag(self, flag_key: str) -> None:
        pattern = f"ff:eval:{flag_key}:*"
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def ping(self) -> bool:
        return bool(self._client.ping())

    def clear(self) -> None:
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match="ff:eval:*", count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break


def build_cache(settings: Settings) -> EvaluationCache:
    if settings.redis_url:
        return RedisEvaluationCache(settings)
    return MemoryEvaluationCache(settings)
