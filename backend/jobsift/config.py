from functools import lru_cache

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="JOBSIFT_",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    elasticsearch_url: AnyHttpUrl = AnyHttpUrl("http://elasticsearch:9200")


@lru_cache
def get_settings() -> Settings:
    return Settings()
