from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "feature-flags-api"
    database_url: str = "sqlite:///./feature_flags.db"
    cache_ttl_seconds: int = 60
    cache_maxsize: int = 10_000
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
