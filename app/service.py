from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import EvaluationCache
from app.models import FeatureFlag, UserOverride, utcnow
from app.schemas import FlagCreate, FlagUpdate


class FlagNotFoundError(Exception):
    pass


class FlagConflictError(Exception):
    pass


class OverrideNotFoundError(Exception):
    pass


class FlagService:
    def __init__(self, db: Session, cache: EvaluationCache) -> None:
        self.db = db
        self.cache = cache

    def create_flag(self, payload: FlagCreate) -> FeatureFlag:
        flag = FeatureFlag(
            key=payload.key,
            description=payload.description,
            enabled=payload.enabled,
        )
        self.db.add(flag)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise FlagConflictError(f"Flag '{payload.key}' already exists") from exc
        self.db.refresh(flag)
        self.cache.invalidate_flag(flag.key)
        return flag

    def list_flags(self) -> list[FeatureFlag]:
        return list(self.db.scalars(select(FeatureFlag).order_by(FeatureFlag.key)).all())

    def get_flag(self, key: str) -> FeatureFlag:
        flag = self.db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
        if flag is None:
            raise FlagNotFoundError(f"Flag '{key}' not found")
        return flag

    def update_flag(self, key: str, payload: FlagUpdate) -> FeatureFlag:
        flag = self.get_flag(key)
        if payload.description is not None:
            flag.description = payload.description
        if payload.enabled is not None:
            flag.enabled = payload.enabled
        flag.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(flag)
        self.cache.invalidate_flag(flag.key)
        return flag

    def upsert_override(self, key: str, user_id: str, enabled: bool) -> UserOverride:
        flag = self.get_flag(key)
        override = self.db.scalar(
            select(UserOverride).where(
                UserOverride.flag_id == flag.id,
                UserOverride.user_id == user_id,
            )
        )
        if override is None:
            override = UserOverride(flag_id=flag.id, user_id=user_id, enabled=enabled)
            self.db.add(override)
        else:
            override.enabled = enabled
            override.updated_at = utcnow()
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # Concurrent insert race: fetch winner and update.
            override = self.db.scalar(
                select(UserOverride).where(
                    UserOverride.flag_id == flag.id,
                    UserOverride.user_id == user_id,
                )
            )
            if override is None:
                raise FlagConflictError("Could not upsert override") from exc
            override.enabled = enabled
            override.updated_at = utcnow()
            self.db.commit()
        self.db.refresh(override)
        self.cache.invalidate_flag(flag.key)
        return override

    def delete_override(self, key: str, user_id: str) -> None:
        flag = self.get_flag(key)
        override = self.db.scalar(
            select(UserOverride).where(
                UserOverride.flag_id == flag.id,
                UserOverride.user_id == user_id,
            )
        )
        if override is None:
            raise OverrideNotFoundError(
                f"Override for flag '{key}' and user '{user_id}' not found"
            )
        self.db.delete(override)
        self.db.commit()
        self.cache.invalidate_flag(flag.key)

    def evaluate(self, key: str, user_id: str) -> dict:
        cached = self.cache.get_evaluation(key, user_id)
        if cached is not None:
            return {
                "key": key,
                "user_id": user_id,
                "enabled": cached["enabled"],
                "source": cached["source"],
                "cached": True,
            }

        flag = self.get_flag(key)
        override = self.db.scalar(
            select(UserOverride).where(
                UserOverride.flag_id == flag.id,
                UserOverride.user_id == user_id,
            )
        )
        if override is not None:
            enabled = override.enabled
            source = "override"
        else:
            enabled = flag.enabled
            source = "default"

        self.cache.set_evaluation(key, user_id, enabled, source)
        return {
            "key": key,
            "user_id": user_id,
            "enabled": enabled,
            "source": source,
            "cached": False,
        }
