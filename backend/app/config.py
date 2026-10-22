"""Application settings loaded from environment variables or a .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads the repo-root .env when run from backend/, or a local .env.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://copilot:change-me@localhost:5432/copilot"

    # Signs session JWTs. No default, so a deployment cannot run with a known secret;
    # 32+ characters gives HS256 the 256-bit key it needs.
    jwt_secret: str = Field(min_length=32)
    session_minutes: int = 8 * 60
    # Browsers send Secure cookies only over HTTPS, so enable this when deployed.
    cookie_secure: bool = False
    # Password for the seeded demo users.
    demo_password: str = "demo-password"


@lru_cache
def get_settings() -> Settings:
    return Settings()
