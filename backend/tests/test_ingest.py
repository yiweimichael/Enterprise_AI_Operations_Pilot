from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.integrations.embeddings import FakeEmbedder
from app.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk
from scripts.ingest import ingest
from scripts.seed import DOCUMENTS_DIR, seed


class CountingEmbedder(FakeEmbedder):
    """Records how many texts were sent, to check that unchanged chunks are skipped."""

    def __init__(self, model="fake-hashing-v1"):
        super().__init__(EMBEDDING_DIMENSIONS)
        self.model = model
        self.embedded = 0

    def embed(self, texts):
        self.embedded += len(texts)
        return super().embed(texts)


def write_document(directory: Path, name: str, roles: str, body: str) -> None:
    (directory / name).write_text(
        f"---\ntitle: {name}\nallowed_roles: {roles}\n---\n{body}", encoding="utf-8"
    )


# Selects the table, not the ORM class: `db` is a plain Connection, which returns
# rows of columns rather than ORM objects.
CHUNKS = DocumentChunk.__table__


def chunk_rows(db, source):
    return db.execute(
        select(CHUNKS)
        .join(Document)
        .where(Document.source == source)
        .order_by(CHUNKS.c.chunk_index)
    ).all()


def test_sample_documents_are_chunked_with_exact_locations(db):
    seed(db)
    result = ingest(db, FakeEmbedder(EMBEDDING_DIMENSIONS))

    rows = db.execute(select(CHUNKS, Document.source).join(Document)).all()
    assert len(rows) == result.chunks > result.documents
    for chunk in rows:
        file_text = (DOCUMENTS_DIR / chunk.source).read_text(encoding="utf-8")
        assert file_text[chunk.start_char : chunk.end_char] == chunk.content
        assert chunk.embedding_model == "fake-hashing-v1"
        assert len(chunk.embedding) == EMBEDDING_DIMENSIONS


def test_chunks_inherit_document_permissions(db):
    seed(db)
    ingest(db, FakeEmbedder(EMBEDDING_DIMENSIONS))

    chunks = chunk_rows(db, "discount-approval-matrix.md")

    assert chunks
    assert all(chunk.allowed_roles == ["manager", "admin"] for chunk in chunks)
    assert "Renewal discounts" in {chunk.section for chunk in chunks}


def test_rerunning_embeds_nothing_and_leaves_chunks_untouched(db):
    seed(db)
    ingest(db, CountingEmbedder())
    ids = set(db.execute(select(DocumentChunk.id)).scalars())

    embedder = CountingEmbedder()
    result = ingest(db, embedder)

    assert embedder.embedded == result.embedded == 0
    assert result.unchanged_documents == result.documents
    assert set(db.execute(select(DocumentChunk.id)).scalars()) == ids


def test_editing_one_section_reembeds_only_that_chunk(db, tmp_path):
    body = "# Guide\n\n## A\nFirst.\n\n## B\nSecond.\n"
    write_document(tmp_path, "guide.md", "[analyst, manager, admin]", body)
    seed(db, tmp_path)
    ingest(db, CountingEmbedder(), tmp_path)

    edited = body.replace("First", "Updated")
    write_document(tmp_path, "guide.md", "[analyst, manager, admin]", edited)
    embedder = CountingEmbedder()
    ingest(db, embedder, tmp_path)

    assert embedder.embedded == 1
    contents = [chunk.content for chunk in chunk_rows(db, "guide.md")]
    assert contents == ["# Guide", "## A\nUpdated.", "## B\nSecond."]


def test_changing_the_model_reembeds_everything(db, tmp_path):
    write_document(tmp_path, "guide.md", "[admin]", "# Guide\n\n## A\nFirst.\n\n## B\nSecond.\n")
    seed(db, tmp_path)
    ingest(db, CountingEmbedder(), tmp_path)

    embedder = CountingEmbedder(model="another-model")
    ingest(db, embedder, tmp_path)

    assert embedder.embedded == 3
    assert {c.embedding_model for c in chunk_rows(db, "guide.md")} == {"another-model"}


def test_deleted_files_lose_their_chunks(db, tmp_path):
    write_document(tmp_path, "a.md", "[admin]", "# A\nText.")
    write_document(tmp_path, "b.md", "[admin]", "# B\nText.")
    seed(db, tmp_path)
    ingest(db, FakeEmbedder(EMBEDDING_DIMENSIONS), tmp_path)

    (tmp_path / "b.md").unlink()
    seed(db, tmp_path)
    ingest(db, FakeEmbedder(EMBEDDING_DIMENSIONS), tmp_path)

    assert db.execute(select(func.count()).select_from(DocumentChunk)).scalar_one() == 1


def test_unseeded_documents_are_reported(db, tmp_path):
    write_document(tmp_path, "new.md", "[admin]", "# New\nText.")

    with pytest.raises(ValueError, match="new.md"):
        ingest(db, FakeEmbedder(EMBEDDING_DIMENSIONS), tmp_path)


def test_embedder_size_must_match_the_column(db):
    with pytest.raises(ValueError, match="dimensions"):
        ingest(db, FakeEmbedder(EMBEDDING_DIMENSIONS + 1))
