"""Seed demo users and sample document records.

Run from backend/:  python -m scripts.seed

Demo users sign in with DEMO_PASSWORD from the environment.

Safe to run repeatedly: users are upserted by email and documents by file name.
Documents whose files were deleted are removed along with their chunks. Users are
never removed, because audit logs must keep referring to them. Chunks and
embeddings are created by ingestion (Phase 3), not here.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import Connection, delete, func
from sqlalchemy.dialects.postgresql import insert

from app.auth import hash_password
from app.config import get_settings
from app.database import engine
from app.models import ROLES, Document, User

DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"

DEMO_USERS = [
    {"email": "analyst@example.com", "display_name": "Ana Analyst", "role": "analyst"},
    {"email": "manager@example.com", "display_name": "Max Manager", "role": "manager"},
    {"email": "admin@example.com", "display_name": "Ada Admin", "role": "admin"},
]


@dataclass(frozen=True)
class DocumentFile:
    source: str
    title: str
    allowed_roles: list[str]
    body: str


@dataclass(frozen=True)
class SeedResult:
    users: int
    documents: int
    removed_documents: int


def read_document(path: Path) -> DocumentFile:
    """Parse a Markdown file with title and allowed_roles front matter."""
    content = path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if not content.startswith("---") or len(parts) < 3:
        raise ValueError(f"{path.name}: missing front matter")

    metadata = yaml.safe_load(parts[1]) or {}
    title = metadata.get("title")
    roles = metadata.get("allowed_roles")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{path.name}: front matter needs a title")
    if not isinstance(roles, list) or not roles or not set(roles) <= set(ROLES):
        raise ValueError(f"{path.name}: allowed_roles must be a non-empty list from {ROLES}")

    return DocumentFile(
        source=path.name,
        title=title.strip(),
        allowed_roles=sorted(set(roles), key=ROLES.index),
        body=parts[2].strip(),
    )


def load_documents(directory: Path = DOCUMENTS_DIR) -> list[DocumentFile]:
    return [read_document(path) for path in sorted(directory.glob("*.md"))]


def seed(connection: Connection, directory: Path = DOCUMENTS_DIR) -> SeedResult:
    password_hash = hash_password(get_settings().demo_password)
    users = insert(User).values([{**user, "password_hash": password_hash} for user in DEMO_USERS])
    connection.execute(
        users.on_conflict_do_update(
            index_elements=[User.email],
            set_={
                "display_name": users.excluded.display_name,
                "role": users.excluded.role,
                "password_hash": users.excluded.password_hash,
            },
        )
    )

    documents = load_documents(directory)
    if documents:
        rows = insert(Document).values(
            [
                {"source": doc.source, "title": doc.title, "allowed_roles": doc.allowed_roles}
                for doc in documents
            ]
        )
        connection.execute(
            rows.on_conflict_do_update(
                index_elements=[Document.source],
                set_={
                    "title": rows.excluded.title,
                    "allowed_roles": rows.excluded.allowed_roles,
                    "updated_at": func.now(),
                },
                # Leave unchanged documents untouched so updated_at stays meaningful.
                where=Document.title.is_distinct_from(rows.excluded.title)
                | Document.allowed_roles.is_distinct_from(rows.excluded.allowed_roles),
            )
        )

    removed = connection.execute(
        delete(Document).where(Document.source.not_in([doc.source for doc in documents]))
    ).rowcount

    return SeedResult(users=len(DEMO_USERS), documents=len(documents), removed_documents=removed)


def main() -> None:
    with engine.begin() as connection:
        result = seed(connection)
    print(
        f"Seeded {result.users} users and {result.documents} documents; "
        f"removed {result.removed_documents} documents whose files no longer exist."
    )


if __name__ == "__main__":
    main()
