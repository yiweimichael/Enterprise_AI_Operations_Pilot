"""Application settings loaded from environment variables or a .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Reads the repo-root .env when run from backend/, or a local .env.
    # Blank values (KEY=) count as unset, so an untouched .env.example line keeps the default.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", env_ignore_empty=True
    )

    database_url: str = "postgresql+psycopg://copilot:change-me@localhost:5432/copilot"

    # Signs session JWTs. No default, so a deployment cannot run with a known secret;
    # 32+ characters gives HS256 the 256-bit key it needs.
    jwt_secret: str = Field(min_length=32)
    session_minutes: int = 8 * 60
    # Browsers send Secure cookies only over HTTPS, so enable this when deployed.
    cookie_secure: bool = False
    # Password for the seeded demo users.
    demo_password: str = "demo-password"

    # "fake" needs no API key and gives deterministic vectors, for tests and offline demos.
    embedding_provider: Literal["openai", "fake"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: SecretStr | None = None

    # Passages less similar than this are not returned, so an unsupported question gets
    # "insufficient evidence" instead of a weak match. Calibrated for
    # text-embedding-3-small on the sample documents: answerable questions scored
    # 0.57-0.77, unrelated ones 0.10-0.45. Recalibrate when the model changes.
    retrieval_min_similarity: float = Field(default=0.5, ge=-1, le=1)
    retrieval_top_k: int = Field(default=5, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    return Settings()
