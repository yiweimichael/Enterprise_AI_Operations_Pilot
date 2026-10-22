from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app


@pytest.fixture
def db() -> Iterator[Connection]:
    """A connection to the migrated database; everything is rolled back after the test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def client(db: Connection) -> Iterator[TestClient]:
    """An API client whose requests use the test's `db` connection, so they are rolled back too."""

    def get_test_db() -> Iterator[Session]:
        with Session(bind=db, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = get_test_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db)
