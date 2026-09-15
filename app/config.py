from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "feature-flags-api"
    environment: str = "development"  # development | production
    database_url: str = "sqlite:///./feature_flags.db"
    redis_url: str = ""  # empty => in-process TTL cache
    cache_ttl_seconds: int = 60
    cache_maxsize: int = 10_000
    api_key: str = ""  # empty => auth disabled (dev only)
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    run_migrations_on_startup: bool = True

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalize DO/Heroku-style URLs for SQLAlchemy + psycopg."""
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
