def test_live(client):
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] == "up"
    assert body["cache"] == "up"
    assert body["cache_backend"] == "memory"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_create_and_get_flag(client):
    create = client.post(
        "/flags",
        json={"key": "new-checkout", "description": "Checkout redesign", "enabled": False},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["key"] == "new-checkout"
    assert body["enabled"] is False

    fetched = client.get("/flags/new-checkout")
    assert fetched.status_code == 200
    assert fetched.json()["key"] == "new-checkout"


def test_duplicate_flag_returns_409(client):
    payload = {"key": "dup-flag", "enabled": True}
    assert client.post("/flags", json=payload).status_code == 201
    conflict = client.post("/flags", json=payload)
    assert conflict.status_code == 409


def test_invalid_flag_key_returns_422(client):
    response = client.post("/flags", json={"key": "bad key!", "enabled": True})
    assert response.status_code == 422


def test_missing_flag_returns_404(client):
    assert client.get("/flags/missing").status_code == 404
    assert client.get("/evaluate/missing", params={"user_id": "u1"}).status_code == 404


def test_evaluate_uses_global_default(client):
    client.post("/flags", json={"key": "dark-mode", "enabled": True})
    response = client.get("/evaluate/dark-mode", params={"user_id": "user-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["source"] == "rollout"
    assert body["bucket"] is not None
    assert body["cached"] is False


def test_evaluate_override_precedence_and_cache(client):
    client.post("/flags", json={"key": "beta", "enabled": False})
    client.put("/flags/beta/users/alice", json={"enabled": True})

    first = client.get("/evaluate/beta", params={"user_id": "alice"})
    assert first.status_code == 200
    assert first.json() == {
        "key": "beta",
        "user_id": "alice",
        "enabled": True,
        "source": "override",
        "bucket": None,
        "cached": False,
    }

    second = client.get("/evaluate/beta", params={"user_id": "alice"})
    assert second.json()["cached"] is True
    assert second.json()["enabled"] is True


def test_cache_invalidated_after_global_update(client):
    client.post("/flags", json={"key": "search", "enabled": False})
    miss = client.get("/evaluate/search", params={"user_id": "u1"})
    assert miss.json()["enabled"] is False
    assert miss.json()["cached"] is False
    assert miss.json()["source"] == "default"

    hit = client.get("/evaluate/search", params={"user_id": "u1"})
    assert hit.json()["cached"] is True

    patched = client.patch("/flags/search", json={"enabled": True})
    assert patched.status_code == 200

    after = client.get("/evaluate/search", params={"user_id": "u1"})
    assert after.json()["enabled"] is True
    assert after.json()["source"] == "rollout"
    assert after.json()["cached"] is False


def test_delete_override_falls_back_to_default(client):
    client.post("/flags", json={"key": "ads", "enabled": True})
    client.put("/flags/ads/users/bob", json={"enabled": False})
    assert client.get("/evaluate/ads", params={"user_id": "bob"}).json()["enabled"] is False

    deleted = client.delete("/flags/ads/users/bob")
    assert deleted.status_code == 204

    eval_response = client.get("/evaluate/ads", params={"user_id": "bob"})
    assert eval_response.json()["enabled"] is True
    assert eval_response.json()["source"] == "rollout"


def test_evaluate_requires_user_id(client):
    client.post("/flags", json={"key": "x", "enabled": True})
    assert client.get("/evaluate/x").status_code == 422


def test_list_flags(client):
    client.post("/flags", json={"key": "a", "enabled": True})
    client.post("/flags", json={"key": "b", "enabled": False})
    response = client.get("/flags")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["items"]}
    assert keys == {"a", "b"}


def test_empty_patch_rejected(client):
    client.post("/flags", json={"key": "patch-me", "enabled": False})
    response = client.patch("/flags/patch-me", json={})
    assert response.status_code == 422


def test_request_id_header(client):
    response = client.get("/live")
    assert "x-request-id" in response.headers


def test_auth_required_when_configured(auth_client):
    denied = auth_client.post("/flags", json={"key": "secure", "enabled": True})
    assert denied.status_code == 401

    allowed = auth_client.post(
        "/flags",
        json={"key": "secure", "enabled": True},
        headers={"X-API-Key": "test-secret"},
    )
    assert allowed.status_code == 201

    assert auth_client.get("/health").status_code == 200
    assert auth_client.get("/ready").status_code == 200
    assert auth_client.get("/live").status_code == 200


def test_create_defaults_rollout_percent_100(client):
    created = client.post("/flags", json={"key": "full-rollout", "enabled": True})
    assert created.status_code == 201
    assert created.json()["rollout_percent"] == 100


def test_kill_switch_disables_even_at_100_percent(client):
    client.post(
        "/flags",
        json={"key": "kill", "enabled": False, "rollout_percent": 100},
    )
    body = client.get("/evaluate/kill", params={"user_id": "anyone"}).json()
    assert body["enabled"] is False
    assert body["source"] == "default"
    assert body["bucket"] is None


def test_rollout_percent_zero_disables_all(client):
    client.post(
        "/flags",
        json={"key": "zero", "enabled": True, "rollout_percent": 0},
    )
    body = client.get("/evaluate/zero", params={"user_id": "anyone"}).json()
    assert body["enabled"] is False
    assert body["source"] == "rollout"
    assert body["bucket"] is not None


def test_rollout_percent_100_enables_all(client):
    client.post(
        "/flags",
        json={"key": "all", "enabled": True, "rollout_percent": 100},
    )
    for user in ("a", "b", "c"):
        body = client.get("/evaluate/all", params={"user_id": user}).json()
        assert body["enabled"] is True
        assert body["source"] == "rollout"


def test_rollout_bucket_stable_for_same_user(client):
    client.post(
        "/flags",
        json={"key": "stable", "enabled": True, "rollout_percent": 50},
    )
    first = client.get("/evaluate/stable", params={"user_id": "alice"}).json()
    second = client.get("/evaluate/stable", params={"user_id": "alice"}).json()
    assert first["bucket"] == second["bucket"]
    assert first["enabled"] == second["enabled"]
    assert second["cached"] is True


def test_different_flags_different_buckets_for_same_user(client):
    client.post("/flags", json={"key": "flag-a", "enabled": True, "rollout_percent": 50})
    client.post("/flags", json={"key": "flag-b", "enabled": True, "rollout_percent": 50})
    a = client.get("/evaluate/flag-a", params={"user_id": "same-user"}).json()
    b = client.get("/evaluate/flag-b", params={"user_id": "same-user"}).json()
    from app.rollout import rollout_bucket

    assert a["bucket"] == rollout_bucket("flag-a", "same-user")
    assert b["bucket"] == rollout_bucket("flag-b", "same-user")
    assert a["bucket"] != b["bucket"]


def test_override_on_beats_zero_percent(client):
    client.post("/flags", json={"key": "force-on", "enabled": True, "rollout_percent": 0})
    client.put("/flags/force-on/users/qa", json={"enabled": True})
    body = client.get("/evaluate/force-on", params={"user_id": "qa"}).json()
    assert body["enabled"] is True
    assert body["source"] == "override"


def test_override_off_beats_full_percent(client):
    client.post("/flags", json={"key": "force-off", "enabled": True, "rollout_percent": 100})
    client.put("/flags/force-off/users/qa", json={"enabled": False})
    body = client.get("/evaluate/force-off", params={"user_id": "qa"}).json()
    assert body["enabled"] is False
    assert body["source"] == "override"


def test_patch_rollout_percent_invalidates_cache(client):
    client.post(
        "/flags",
        json={"key": "ramp", "enabled": True, "rollout_percent": 0},
    )
    before = client.get("/evaluate/ramp", params={"user_id": "u1"}).json()
    assert before["enabled"] is False
    assert client.get("/evaluate/ramp", params={"user_id": "u1"}).json()["cached"] is True

    patched = client.patch("/flags/ramp", json={"rollout_percent": 100})
    assert patched.status_code == 200
    assert patched.json()["rollout_percent"] == 100

    after = client.get("/evaluate/ramp", params={"user_id": "u1"}).json()
    assert after["enabled"] is True
    assert after["cached"] is False
    assert after["source"] == "rollout"


def test_rollout_percent_out_of_range_rejected(client):
    bad_create = client.post(
        "/flags",
        json={"key": "bad-pct", "enabled": True, "rollout_percent": 101},
    )
    assert bad_create.status_code == 422

    client.post("/flags", json={"key": "ok-pct", "enabled": True, "rollout_percent": 10})
    bad_patch = client.patch("/flags/ok-pct", json={"rollout_percent": -1})
    assert bad_patch.status_code == 422
