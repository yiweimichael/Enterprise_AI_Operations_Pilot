from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Document, User
from scripts.seed import load_documents, seed


def write_document(directory: Path, name: str, roles: str) -> None:
    (directory / name).write_text(
        f"---\ntitle: {name}\nallowed_roles: {roles}\n---\n# {name}\n\nBody.\n", encoding="utf-8"
    )


def count(db, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def test_sample_documents_have_mixed_permissions():
    documents = load_documents()
    role_sets = {tuple(doc.allowed_roles) for doc in documents}

    assert 10 <= len(documents) <= 20
    assert ("analyst", "manager", "admin") in role_sets
    assert ("manager", "admin") in role_sets
    assert ("admin",) in role_sets


def test_sample_documents_include_a_prompt_injection_case():
    bodies = [doc.body.lower() for doc in load_documents()]

    assert any("ignore all previous instructions" in body for body in bodies)


def test_seed_creates_one_demo_user_per_role(db):
    seed(db)

    roles = db.execute(select(User.role).where(User.email.like("%@example.com"))).scalars()
    assert sorted(roles) == ["admin", "analyst", "manager"]


def test_seed_loads_every_document_file(db):
    seed(db)

    sources = set(db.execute(select(Document.source)).scalars())
    assert sources == {doc.source for doc in load_documents()}


def test_seed_can_run_repeatedly(db):
    seed(db)
    users, documents = count(db, User), count(db, Document)

    result = seed(db)

    assert (count(db, User), count(db, Document)) == (users, documents)
    assert result.removed_documents == 0


def test_seed_updates_permissions_and_removes_deleted_files(db, tmp_path):
    write_document(tmp_path, "a.md", "[analyst, manager, admin]")
    write_document(tmp_path, "b.md", "[admin]")
    seed(db, tmp_path)

    write_document(tmp_path, "a.md", "[manager]")
    (tmp_path / "b.md").unlink()
    result = seed(db, tmp_path)

    assert dict(db.execute(select(Document.source, Document.allowed_roles)).all()) == {
        "a.md": ["manager"]
    }
    assert result.removed_documents == 1


@pytest.mark.parametrize(
    "front_matter",
    [
        "title: Bad\nallowed_roles: [intern]",
        "title: Bad\nallowed_roles: []",
        "allowed_roles: [admin]",
    ],
)
def test_invalid_front_matter_is_rejected(tmp_path, front_matter):
    (tmp_path / "bad.md").write_text(f"---\n{front_matter}\n---\nBody\n", encoding="utf-8")

    with pytest.raises(ValueError, match="bad.md"):
        load_documents(tmp_path)
