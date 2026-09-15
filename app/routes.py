import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.cache import EvaluationCache, RedisEvaluationCache
from app.db import check_db, get_db
from app.deps import get_cache
from app.schemas import (
    EvaluateResponse,
    FlagCreate,
    FlagListResponse,
    FlagResponse,
    FlagUpdate,
    HealthResponse,
    LiveResponse,
    OverrideResponse,
    OverrideUpsert,
    ReadyResponse,
)
from app.service import (
    FlagConflictError,
    FlagNotFoundError,
    FlagService,
    OverrideNotFoundError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    db: Session = Depends(get_db),
    cache: EvaluationCache = Depends(get_cache),
) -> FlagService:
    return FlagService(db=db, cache=cache)


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="alive")


@router.get("/ready", response_model=ReadyResponse)
def ready(cache: EvaluationCache = Depends(get_cache)) -> ReadyResponse:
    db_ok = check_db()
    try:
        cache_ok = cache.ping()
    except Exception:
        logger.exception("Cache ping failed")
        cache_ok = False

    backend = "redis" if isinstance(cache, RedisEvaluationCache) else "memory"
    if db_ok and cache_ok:
        return ReadyResponse(
            status="ready",
            database="up",
            cache="up",
            cache_backend=backend,
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "status": "not_ready",
            "database": "up" if db_ok else "down",
            "cache": "up" if cache_ok else "down",
            "cache_backend": backend,
        },
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Backward-compatible combined check (DB). Prefer /live and /ready in production."""
    if check_db():
        return HealthResponse(status="ok", database="up")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"status": "degraded", "database": "down"},
    )


@router.post(
    "/flags",
    response_model=FlagResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_flag(
    payload: FlagCreate, service: FlagService = Depends(get_service)
) -> FlagResponse:
    try:
        flag = service.create_flag(payload)
    except FlagConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    logger.info("flag_created key=%s enabled=%s", flag.key, flag.enabled)
    return FlagResponse.model_validate(flag)


@router.get("/flags", response_model=FlagListResponse)
def list_flags(service: FlagService = Depends(get_service)) -> FlagListResponse:
    flags = service.list_flags()
    return FlagListResponse(items=[FlagResponse.model_validate(f) for f in flags])


@router.get("/flags/{key}", response_model=FlagResponse)
def get_flag(key: str, service: FlagService = Depends(get_service)) -> FlagResponse:
    try:
        flag = service.get_flag(key)
    except FlagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FlagResponse.model_validate(flag)


@router.patch("/flags/{key}", response_model=FlagResponse)
def update_flag(
    key: str, payload: FlagUpdate, service: FlagService = Depends(get_service)
) -> FlagResponse:
    try:
        flag = service.update_flag(key, payload)
    except FlagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    logger.info("flag_updated key=%s enabled=%s", flag.key, flag.enabled)
    return FlagResponse.model_validate(flag)


@router.put("/flags/{key}/users/{user_id}", response_model=OverrideResponse)
def upsert_override(
    key: str,
    user_id: str,
    payload: OverrideUpsert,
    service: FlagService = Depends(get_service),
) -> OverrideResponse:
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id must not be empty",
        )
    try:
        override = service.upsert_override(key, user_id, payload.enabled)
    except FlagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    logger.info(
        "override_upserted key=%s user_id=%s enabled=%s",
        key,
        user_id,
        payload.enabled,
    )
    return OverrideResponse(
        flag_key=key,
        user_id=override.user_id,
        enabled=override.enabled,
        created_at=override.created_at,
        updated_at=override.updated_at,
    )


@router.delete(
    "/flags/{key}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_override(
    key: str, user_id: str, service: FlagService = Depends(get_service)
) -> None:
    try:
        service.delete_override(key, user_id)
    except FlagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OverrideNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    logger.info("override_deleted key=%s user_id=%s", key, user_id)


@router.get("/evaluate/{key}", response_model=EvaluateResponse)
def evaluate_flag(
    key: str,
    user_id: str = Query(..., min_length=1, max_length=128),
    service: FlagService = Depends(get_service),
) -> EvaluateResponse:
    try:
        result = service.evaluate(key, user_id)
    except FlagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EvaluateResponse(**result)
