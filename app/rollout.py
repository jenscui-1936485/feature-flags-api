"""Deterministic percentage-rollout bucketing."""

from __future__ import annotations

import hashlib


def rollout_bucket(flag_key: str, user_id: str) -> int:
    """Stable bucket in 0..99 from SHA-256(flag_key:user_id)."""
    digest = hashlib.sha256(f"{flag_key}:{user_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100
