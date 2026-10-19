from collections.abc import Iterator

import pytest
from sqlalchemy import Connection

from app.database import engine


@pytest.fixture
def db() -> Iterator[Connection]:
    """A connection to the migrated database; everything is rolled back after the test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
