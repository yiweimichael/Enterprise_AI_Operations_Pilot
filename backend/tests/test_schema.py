"""Database rules enforced by migration 0002, independent of application code."""

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from app.models import EMBEDDING_DIMENSIONS

EMBEDDING = "[" + ",".join(["0.1"] * EMBEDDING_DIMENSIONS) + "]"


def insert_document(db: Connection, allowed_roles: list[str]) -> str:
    return db.execute(
        text(
            "INSERT INTO documents (title, source, allowed_roles) "
            "VALUES ('Policy', 'policy.md', :roles) RETURNING id"
        ),
        {"roles": allowed_roles},
    ).scalar_one()


def insert_chunk(db: Connection, document_id: str, allowed_roles: list[str] | None = None) -> str:
    columns = "document_id, chunk_index, content, content_hash, embedding, embedding_model, "
    columns += "start_char, end_char"
    values = ":document_id, 0, 'text', 'hash', :embedding, 'test-model', 0, 4"
    if allowed_roles is not None:
        columns += ", allowed_roles"
        values += ", :roles"
    return db.execute(
        text(f"INSERT INTO document_chunks ({columns}) VALUES ({values}) RETURNING id"),
        {"document_id": document_id, "embedding": EMBEDDING, "roles": allowed_roles},
    ).scalar_one()


def chunk_roles(db: Connection, chunk_id: str) -> list[str]:
    return db.execute(
        text("SELECT allowed_roles FROM document_chunks WHERE id = :id"), {"id": chunk_id}
    ).scalar_one()


def test_chunk_inherits_document_roles_even_when_insert_sets_others(db):
    document_id = insert_document(db, ["manager"])

    chunk_id = insert_chunk(db, document_id, allowed_roles=["analyst", "manager", "admin"])

    assert chunk_roles(db, chunk_id) == ["manager"]


def test_chunk_roles_cannot_be_changed_directly(db):
    document_id = insert_document(db, ["manager"])
    chunk_id = insert_chunk(db, document_id)

    db.execute(
        text("UPDATE document_chunks SET allowed_roles = ARRAY['analyst'] WHERE id = :id"),
        {"id": chunk_id},
    )

    assert chunk_roles(db, chunk_id) == ["manager"]


def test_document_role_change_propagates_to_chunks(db):
    document_id = insert_document(db, ["analyst", "manager"])
    chunk_id = insert_chunk(db, document_id)

    db.execute(
        text("UPDATE documents SET allowed_roles = ARRAY['admin'] WHERE id = :id"),
        {"id": document_id},
    )

    assert chunk_roles(db, chunk_id) == ["admin"]


@pytest.mark.parametrize("allowed_roles", [[], ["intern"], ["analyst", "intern"]])
def test_documents_reject_empty_or_unknown_roles(db, allowed_roles):
    with pytest.raises(DBAPIError, match="ck_documents_allowed_roles"):
        insert_document(db, allowed_roles)


def test_users_reject_unknown_role(db):
    with pytest.raises(DBAPIError, match="ck_users_role"):
        db.execute(
            text(
                "INSERT INTO users (email, display_name, role) "
                "VALUES ('x@example.com', 'X', 'superuser')"
            )
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_logs SET event_type = 'edited'",
        "DELETE FROM audit_logs",
        "TRUNCATE audit_logs",
    ],
)
def test_audit_logs_are_append_only(db, statement):
    db.execute(text("INSERT INTO audit_logs (event_type) VALUES ('login')"))

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text(statement))
