"""Create users, documents, document_chunks, and audit_logs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of app.models constants, so this migration never changes.
ROLE_LIST = "'analyst', 'manager', 'admin'"
ROLE_ARRAY = f"ARRAY[{ROLE_LIST}]::text[]"
EMBEDDING_DIMENSIONS = 1024


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.func.gen_random_uuid(),
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text()),
        _created_at(),
        sa.CheckConstraint(f"role IN ({ROLE_LIST})", name="ck_users_role"),
    )

    op.create_table(
        "documents",
        _uuid_pk(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, unique=True),
        sa.Column("allowed_roles", postgresql.ARRAY(sa.Text()), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            f"cardinality(allowed_roles) > 0 AND allowed_roles <@ {ROLE_ARRAY}",
            name="ck_documents_allowed_roles",
        ),
    )

    op.create_table(
        "document_chunks",
        _uuid_pk(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column(
            "allowed_roles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("section", sa.Text()),
        sa.Column("page", sa.Integer()),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        _created_at(),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_position"),
        sa.CheckConstraint(
            "start_char >= 0 AND end_char > start_char", name="ck_document_chunks_char_range"
        ),
    )
    op.create_index(
        "ix_document_chunks_embedding",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_document_chunks_allowed_roles",
        "document_chunks",
        ["allowed_roles"],
        postgresql_using="gin",
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text()),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])

    # Chunk permissions always come from the parent document. Any value an
    # INSERT or UPDATE tries to set is replaced, so ingestion code cannot get it wrong.
    op.execute(
        """
        CREATE FUNCTION document_chunks_inherit_allowed_roles() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            SELECT allowed_roles INTO NEW.allowed_roles
            FROM documents WHERE id = NEW.document_id;
            RETURN NEW;
        END;
        $$;

        CREATE TRIGGER trg_document_chunks_inherit_allowed_roles
        BEFORE INSERT OR UPDATE OF document_id, allowed_roles ON document_chunks
        FOR EACH ROW EXECUTE FUNCTION document_chunks_inherit_allowed_roles();
        """
    )

    # Changing a document's permissions updates its chunks in the same transaction.
    op.execute(
        """
        CREATE FUNCTION documents_propagate_allowed_roles() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE document_chunks SET allowed_roles = NEW.allowed_roles
            WHERE document_id = NEW.id;
            RETURN NULL;
        END;
        $$;

        CREATE TRIGGER trg_documents_propagate_allowed_roles
        AFTER UPDATE OF allowed_roles ON documents
        FOR EACH ROW WHEN (OLD.allowed_roles IS DISTINCT FROM NEW.allowed_roles)
        EXECUTE FUNCTION documents_propagate_allowed_roles();
        """
    )

    # Audit history is append-only.
    op.execute(
        """
        CREATE FUNCTION audit_logs_reject_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only; % is not allowed', TG_OP;
        END;
        $$;

        CREATE TRIGGER trg_audit_logs_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_reject_change();

        CREATE TRIGGER trg_audit_logs_no_truncate
        BEFORE TRUNCATE ON audit_logs
        FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_reject_change();
        """
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.execute("DROP FUNCTION audit_logs_reject_change()")
    op.execute("DROP FUNCTION documents_propagate_allowed_roles()")
    op.execute("DROP FUNCTION document_chunks_inherit_allowed_roles()")
