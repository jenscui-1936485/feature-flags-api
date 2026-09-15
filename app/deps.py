from functools import lru_cache

from app.cache import EvaluationCache
from app.config import get_settings


@lru_cache
def get_cache() -> EvaluationCache:
    return EvaluationCache(get_settings())
