import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db
from app.routes import router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    logger.info("starting app database_url=%s", settings.database_url.split("://")[0])
    init_db()
    logger.info("database ready")
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Feature Flags API",
        version="1.0.0",
        description="Production-minded feature flag service for DigitalOcean interview.",
        lifespan=lifespan,
    )
    application.include_router(router)
    return application


app = create_app()
