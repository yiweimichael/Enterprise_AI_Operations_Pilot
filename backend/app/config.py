"""Application settings loaded from environment variables or a .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads the repo-root .env when run from backend/, or a local .env.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://copilot:change-me@localhost:5432/copilot"


@lru_cache
def get_settings() -> Settings:
    return Settings()
