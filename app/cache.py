from threading import Lock
from typing import Any

from cachetools import TTLCache

from app.config import Settings


class EvaluationCache:
    """In-process TTL cache for flag evaluation results."""

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

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
