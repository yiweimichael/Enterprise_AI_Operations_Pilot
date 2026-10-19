"""Reset the local database: drop everything, migrate to head, and reseed.

Run from backend/:  python -m scripts.reset_db

Deletes all data, including audit logs. Refuses to run unless DATABASE_URL
points at this machine, so it can never wipe a cloud database.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.database import engine
from scripts.seed import seed

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def ensure_local_database(database_url: str) -> None:
    host = make_url(database_url).host
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"Refusing to reset a non-local database (host: {host!r}).")


def main() -> None:
    ensure_local_database(get_settings().database_url)

    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    with engine.begin() as connection:
        result = seed(connection)
    print(f"Reset the database and seeded {result.users} users and {result.documents} documents.")


if __name__ == "__main__":
    main()
