from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

FLAG_KEY_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$"


class FlagCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=64, pattern=FLAG_KEY_PATTERN)
    description: str = Field(default="", max_length=1024)
    enabled: bool = False


class FlagUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=1024)
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> Self:
        if self.description is None and self.enabled is None:
            raise ValueError("At least one of enabled or description must be provided")
        return self


class FlagResponse(BaseModel):
    id: str
    key: str
    description: str
    enabled: bool
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
    source: Literal["override", "default"]
    cached: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
