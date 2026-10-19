import pytest

from scripts.reset_db import ensure_local_database


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://copilot:secret@localhost:5432/copilot",
        "postgresql+psycopg://copilot:secret@127.0.0.1/copilot",
    ],
)
def test_allows_local_databases(url):
    ensure_local_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://copilot:secret@pilot-db.postgres.database.azure.com:5432/copilot",
        "postgresql+psycopg://copilot:secret@10.0.0.5:5432/copilot",
        "postgresql+psycopg://copilot:secret@/copilot",
    ],
)
def test_refuses_other_databases(url):
    with pytest.raises(SystemExit, match="Refusing to reset"):
        ensure_local_database(url)
