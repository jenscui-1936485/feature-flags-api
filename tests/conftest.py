from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cache import MemoryEvaluationCache
from app.config import Settings
from app.db import Base, get_db
from app.deps import get_cache
from app.main import create_app


def _build_client(settings: Settings) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    cache = MemoryEvaluationCache(settings)
    app = create_app(settings)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache] = lambda: cache
    return TestClient(app)


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        environment="development",
        api_key="",
        redis_url="",
        cache_ttl_seconds=60,
        cache_maxsize=1000,
        run_migrations_on_startup=False,
    )


@pytest.fixture()
def client(settings: Settings) -> Generator[TestClient, None, None]:
    with _build_client(settings) as test_client:
        yield test_client


@pytest.fixture()
def auth_client() -> Generator[TestClient, None, None]:
    settings = Settings(
        environment="development",
        api_key="test-secret",
        redis_url="",
        run_migrations_on_startup=False,
    )
    with _build_client(settings) as test_client:
        yield test_client
