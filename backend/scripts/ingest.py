"""Ingest the sample documents: chunk them, embed the chunks, and store each chunk
with its location in the source.

Run from backend/:  python -m scripts.ingest

Seeds the documents first, so it can run on its own. Safe to run repeatedly: a chunk
is sent to the embedder only when its text or the embedding model has changed, and a
document whose chunks are all unchanged is left untouched.

Location: `start_char` and `end_char` index into the source file's text as Python reads
it (newlines normalized to \\n), so `file_text[start_char:end_char] == content`.
`section` is the nearest heading. `page` stays empty because Markdown has no pages.

Permissions are not set here: a database trigger copies them from the document.
"""

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Connection, delete, insert, select

from app.config import get_settings
from app.database import engine
from app.integrations.embeddings import Embedder, get_embedder
from app.models import EMBEDDING_DIMENSIONS, Document, DocumentChunk
from app.services.chunking import Chunk, chunk_markdown
from scripts.seed import DOCUMENTS_DIR, DocumentFile, load_documents, seed


@dataclass(frozen=True)
class PlannedChunk:
    chunk: Chunk
    # Absolute offsets in the source file.
    start_char: int
    end_char: int
    embedding_input: str
    content_hash: str


@dataclass(frozen=True)
class IngestResult:
    documents: int
    chunks: int
    embedded: int
    unchanged_documents: int


def embedding_input(title: str, chunk: Chunk) -> str:
    """The chunk text with its document title and headings, so the vector carries context.

    Only `content` is stored and cited; this extra context is used for the embedding alone.
    """
    context = [title, *(heading for heading in chunk.headings if heading != title)]
    return "\n".join(context) + "\n\n" + chunk.content


def plan_chunks(document: DocumentFile) -> list[PlannedChunk]:
    planned = []
    for chunk in chunk_markdown(document.body):
        text = embedding_input(document.title, chunk)
        planned.append(
            PlannedChunk(
                chunk=chunk,
                start_char=document.body_start + chunk.start_char,
                end_char=document.body_start + chunk.end_char,
                embedding_input=text,
                # Hashes exactly what is embedded, so a renamed title or heading re-embeds too.
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
            )
        )
    return planned


def ingest(
    connection: Connection, embedder: Embedder, directory: Path = DOCUMENTS_DIR
) -> IngestResult:
    """Chunk and embed every document in `directory`. Documents must already be seeded."""
    if embedder.dimensions != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedder returns {embedder.dimensions} dimensions; "
            f"the database stores {EMBEDDING_DIMENSIONS}."
        )

    files = load_documents(directory)
    document_ids: dict[str, uuid.UUID] = dict(
        connection.execute(
            select(Document.source, Document.id).where(
                Document.source.in_([file.source for file in files])
            )
        ).all()
    )
    missing = [file.source for file in files if file.source not in document_ids]
    if missing:
        raise ValueError(f"Not seeded yet: {', '.join(missing)}. Run python -m scripts.seed.")

    existing = connection.execute(
        select(
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content_hash,
            DocumentChunk.embedding_model,
            DocumentChunk.section,
            DocumentChunk.start_char,
            DocumentChunk.end_char,
            DocumentChunk.embedding,
        ).where(DocumentChunk.document_id.in_(document_ids.values()))
    ).all()

    # Embeddings already stored for this model, reusable for any chunk with the same text.
    cache: dict[str, list[float]] = {
        row.content_hash: list(row.embedding)
        for row in existing
        if row.embedding_model == embedder.model
    }
    stored_layout: dict[uuid.UUID, list[tuple]] = {}
    for row in existing:
        stored_layout.setdefault(row.document_id, []).append(
            (
                row.chunk_index,
                row.content_hash,
                row.embedding_model,
                row.section,
                row.start_char,
                row.end_char,
            )
        )

    plans = {document_ids[file.source]: plan_chunks(file) for file in files}
    changed: dict[uuid.UUID, list[PlannedChunk]] = {}
    for document_id, planned in plans.items():
        layout = [
            (
                p.chunk.index,
                p.content_hash,
                embedder.model,
                p.chunk.section,
                p.start_char,
                p.end_char,
            )
            for p in planned
        ]
        if sorted(layout) != sorted(stored_layout.get(document_id, [])):
            changed[document_id] = planned

    to_embed = {
        p.content_hash: p.embedding_input
        for planned in changed.values()
        for p in planned
        if p.content_hash not in cache
    }
    if to_embed:
        vectors = embedder.embed(list(to_embed.values()))
        if len(vectors) != len(to_embed) or any(
            len(vector) != EMBEDDING_DIMENSIONS for vector in vectors
        ):
            raise ValueError("The embedder returned the wrong number or size of vectors.")
        cache.update(zip(to_embed, vectors, strict=True))

    for document_id, planned in changed.items():
        # Replace the document's chunks as a whole, so indexes and offsets stay consistent.
        connection.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        if planned:
            connection.execute(
                insert(DocumentChunk),
                [
                    {
                        "document_id": document_id,
                        "chunk_index": p.chunk.index,
                        "content": p.chunk.content,
                        "content_hash": p.content_hash,
                        "embedding": cache[p.content_hash],
                        "embedding_model": embedder.model,
                        "section": p.chunk.section,
                        "page": None,
                        "start_char": p.start_char,
                        "end_char": p.end_char,
                    }
                    for p in planned
                ],
            )

    return IngestResult(
        documents=len(files),
        chunks=sum(len(planned) for planned in plans.values()),
        embedded=len(to_embed),
        unchanged_documents=len(files) - len(changed),
    )


def main() -> None:
    settings = get_settings()
    try:
        embedder = get_embedder(settings, EMBEDDING_DIMENSIONS)
    except ValueError as error:
        raise SystemExit(str(error)) from None

    with engine.begin() as connection:
        seed(connection)
        result = ingest(connection, embedder)
    print(
        f"Ingested {result.documents} documents into {result.chunks} chunks with "
        f"{embedder.model}: embedded {result.embedded} new or changed chunks; "
        f"{result.unchanged_documents} documents were already up to date."
    )


if __name__ == "__main__":
    main()
