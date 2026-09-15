from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

FLAG_KEY_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$"


class FlagCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=64, pattern=FLAG_KEY_PATTERN)
    description: str = Field(default="", max_length=1024)
    enabled: bool = False
    rollout_percent: int = Field(default=100, ge=0, le=100)


class FlagUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=1024)
    enabled: bool | None = None
    rollout_percent: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if (
            self.description is None
            and self.enabled is None
            and self.rollout_percent is None
        ):
            raise ValueError(
                "At least one of enabled, description, or rollout_percent must be provided"
            )
        return self


class FlagResponse(BaseModel):
    id: str
    key: str
    description: str
    enabled: bool
    rollout_percent: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FlagListResponse(BaseModel):
    items: list[FlagResponse]


class OverrideUpsert(BaseModel):
    enabled: bool


class OverrideResponse(BaseModel):
    flag_key: str
    user_id: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class EvaluateResponse(BaseModel):
    key: str
    user_id: str
    enabled: bool
    source: Literal["override", "rollout", "default"]
    bucket: int | None = None
    cached: bool

    @field_validator("bucket")
    @classmethod
    def bucket_range(cls, value: int | None) -> int | None:
        if value is not None and not (0 <= value <= 99):
            raise ValueError("bucket must be between 0 and 99")
        return value


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]


class LiveResponse(BaseModel):
    status: Literal["alive"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["up", "down"]
    cache: Literal["up", "down"]
    cache_backend: Literal["memory", "redis"]
