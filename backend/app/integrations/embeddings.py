"""Text embedding providers behind one interface, so tests and evals can swap in a fake."""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any, Protocol

from app.config import Settings


class Embedder(Protocol):
    # Stored with every chunk, so a model change shows which chunks need re-embedding.
    model: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in the same order."""
        ...


class OpenAIEmbedder:
    """OpenAI embeddings, shortened to `dimensions` by the API to fit the vector column."""

    def __init__(
        self,
        model: str,
        dimensions: int,
        api_key: str | None = None,
        client: Any = None,
        batch_size: int = 100,
    ) -> None:
        if client is None:
            from openai import OpenAI

            # The SDK retries rate limits and server errors with backoff.
            client = OpenAI(api_key=api_key, max_retries=5)
        self.model = model
        self.dimensions = dimensions
        self._client = client
        self._batch_size = batch_size

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = self._client.embeddings.create(
                model=self.model, input=batch, dimensions=self.dimensions
            )
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        return vectors


class FakeEmbedder:
    """Deterministic bag-of-words vectors: no network, no API key.

    Texts that share words get similar vectors, so retrieval tests still behave
    sensibly. Not a substitute for a real model's quality.
    """

    model = "fake-hashing-v1"

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in re.findall(r"\w+", text.lower()):
            digest = int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest())
            vector[digest % self.dimensions] += 1.0 if digest >> 63 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            # Cosine distance is undefined for a zero vector.
            vector[0], norm = 1.0, 1.0
        return [value / norm for value in vector]


def get_embedder(settings: Settings, dimensions: int) -> Embedder:
    if settings.embedding_provider == "fake":
        return FakeEmbedder(dimensions)
    if settings.embedding_api_key is None:
        raise ValueError(
            "EMBEDDING_API_KEY is not set. Add an OpenAI API key to .env, "
            "or set EMBEDDING_PROVIDER=fake to use deterministic test vectors."
        )
    return OpenAIEmbedder(
        settings.embedding_model, dimensions, settings.embedding_api_key.get_secret_value()
    )
