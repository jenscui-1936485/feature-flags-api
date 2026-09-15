import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.db import run_migrations
from app.deps import get_cache, reset_cache_singleton
from app.middleware import ApiKeyMiddleware, RequestIdMiddleware
from app.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _validate_production_config(settings: Settings) -> None:
    if not settings.is_production:
        return
    errors: list[str] = []
    if not settings.api_key:
        errors.append("API_KEY is required when ENVIRONMENT=production")
    if settings.database_url.startswith("sqlite"):
        errors.append("DATABASE_URL must be Postgres in production")
    if not settings.redis_url:
        errors.append("REDIS_URL is required when ENVIRONMENT=production")
    if errors:
        for err in errors:
            logger.error("config_error: %s", err)
        sys.exit(1)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    logging.getLogger().setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        _validate_production_config(cfg)
        logger.info(
            "starting app env=%s db=%s cache=%s auth=%s",
            cfg.environment,
            cfg.database_url.split("://")[0],
            "redis" if cfg.redis_url else "memory",
            "enabled" if cfg.auth_enabled else "disabled",
        )
        if cfg.run_migrations_on_startup:
            run_migrations()
        reset_cache_singleton()
        get_cache()
        logger.info("application ready")
        yield

    application = FastAPI(
        title="Feature Flags API",
        version="1.1.0",
        description="Production-minded feature flag service with Postgres, Redis, and API-key auth.",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(ApiKeyMiddleware, settings=cfg)
    application.include_router(router)
    application.state.settings = cfg
    return application


app = create_app()
