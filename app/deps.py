from functools import lru_cache

from app.cache import EvaluationCache, build_cache
from app.config import get_settings


@lru_cache
def get_cache() -> EvaluationCache:
    return build_cache(get_settings())


def reset_cache_singleton() -> None:
    get_cache.cache_clear()
