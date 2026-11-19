"""knowledge_search: retrieves authorized document chunks with citations.

Permissions are enforced inside the SQL query, not after it: chunks whose
`allowed_roles` do not include the user's role are never read, so they cannot be
ranked, returned, or leak through a bug in later code. The role comes from the
signed session (CurrentUser), never from the question.

The nearest-neighbour search uses the HNSW index on `document_chunks.embedding`.
With iterative index scans (pgvector 0.8+), the index keeps scanning until it has
found enough rows that pass the permission filter, so restricted chunks that are
closer to the query cannot crowd authorized ones out of the results.

Passages below the similarity threshold are dropped, so an empty result means the
user has no authorized evidence for the question.
"""

from sqlalchemy import Connection, Select, func, literal, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.embeddings import Embedder
from app.models import Document, DocumentChunk
from app.schemas import CurrentUser, Passage


def search_statement(
    vector: list[float], role: str, embedding_model: str, limit: int, min_similarity: float
) -> Select:
    """The search query, kept separate so tests can check its plan."""
    distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
    # Inner query: only chunks this role may read, nearest first. It touches no other
    # table, so Postgres can answer it straight from the HNSW index.
    nearest = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.section,
            DocumentChunk.page,
            DocumentChunk.start_char,
            DocumentChunk.end_char,
            DocumentChunk.content,
            distance,
        )
        .where(
            DocumentChunk.allowed_roles.contains([role]),
            # Vectors from different models are not comparable.
            DocumentChunk.embedding_model == embedding_model,
        )
        .order_by(distance)
        .limit(limit)
        .subquery()
    )
    return (
        select(nearest, Document.title, Document.source)
        .join(Document, Document.id == nearest.c.document_id)
        .where(nearest.c.distance <= 1 - min_similarity)
        .order_by(nearest.c.distance)
    )


def knowledge_search(
    query: str,
    user: CurrentUser,
    db: Session | Connection,
    embedder: Embedder,
    *,
    limit: int | None = None,
    min_similarity: float | None = None,
) -> list[Passage]:
    """The passages `user` may read that best match `query`, most similar first.

    Returns an empty list when nothing authorized meets `min_similarity`.
    """
    settings = get_settings()
    limit = settings.retrieval_top_k if limit is None else limit
    min_similarity = settings.retrieval_min_similarity if min_similarity is None else min_similarity
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if not query.strip():
        return []

    vector = embedder.embed([query])[0]

    # Transaction-local: strict_order keeps results exactly ordered by distance, and
    # ef_search must be at least the limit or HNSW returns fewer rows than asked for.
    db.execute(
        select(
            func.set_config("hnsw.iterative_scan", "strict_order", literal(True)),
            func.set_config("hnsw.ef_search", str(max(40, limit)), literal(True)),
        )
    )
    rows = db.execute(
        search_statement(vector, user.role, embedder.model, limit, min_similarity)
    ).all()

    return [
        Passage(
            chunk_id=row.id,
            document_id=row.document_id,
            document_title=row.title,
            source=row.source,
            section=row.section,
            page=row.page,
            start_char=row.start_char,
            end_char=row.end_char,
            content=row.content,
            similarity=1 - row.distance,
        )
        for row in rows
    ]
