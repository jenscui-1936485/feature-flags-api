from app.cache import MemoryEvaluationCache
from app.config import Settings


def test_cache_invalidate_flag_prefix():
    cache = MemoryEvaluationCache(Settings(cache_ttl_seconds=60, cache_maxsize=100))
    cache.set_evaluation("alpha", "u1", True, "default")
    cache.set_evaluation("alpha", "u2", False, "override")
    cache.set_evaluation("beta", "u1", True, "default")

    cache.invalidate_flag("alpha")

    assert cache.get_evaluation("alpha", "u1") is None
    assert cache.get_evaluation("alpha", "u2") is None
    assert cache.get_evaluation("beta", "u1") is not None
