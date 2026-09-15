from app.rollout import rollout_bucket


def test_rollout_bucket_deterministic_and_in_range():
    first = rollout_bucket("checkout", "alice")
    second = rollout_bucket("checkout", "alice")
    assert first == second
    assert 0 <= first <= 99


def test_rollout_bucket_includes_flag_key():
    assert rollout_bucket("flag-a", "user-1") != rollout_bucket("flag-b", "user-1")


def test_rollout_bucket_known_vector():
    # Pin algorithm: SHA-256("demo:user-42")[:8] hex → int → % 100
    assert rollout_bucket("demo", "user-42") == int(
        __import__("hashlib")
        .sha256(b"demo:user-42")
        .hexdigest()[:8],
        16,
    ) % 100
