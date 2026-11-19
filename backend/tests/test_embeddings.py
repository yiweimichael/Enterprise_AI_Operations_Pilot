import math
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.integrations.embeddings import FakeEmbedder, OpenAIEmbedder, get_embedder


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embedder_is_deterministic_and_normalized():
    embedder = FakeEmbedder(64)

    first = embedder.embed(["Hotel limit per night"])
    again = embedder.embed(["Hotel limit per night"])

    assert first == again
    assert len(first[0]) == 64
    assert math.isclose(math.sqrt(sum(v * v for v in first[0])), 1.0)


def test_fake_embedder_scores_shared_words_higher():
    query, related, unrelated = FakeEmbedder(1024).embed(
        ["hotel limit per night", "the hotel limit is $250 per night", "rotate the vpn keys"]
    )

    assert cosine(query, related) > cosine(query, unrelated)


def test_fake_embedder_never_returns_a_zero_vector():
    assert any(FakeEmbedder(8).embed(["!!!"])[0])


class StubClient:
    def __init__(self):
        self.calls = []
        self.embeddings = self

    def create(self, model, input, dimensions):
        self.calls.append((model, list(input), dimensions))
        # Returned out of order, as the API does not promise ordering.
        data = [SimpleNamespace(index=i, embedding=[float(len(t))]) for i, t in enumerate(input)]
        return SimpleNamespace(data=list(reversed(data)))


def test_openai_embedder_batches_and_keeps_input_order():
    client = StubClient()
    embedder = OpenAIEmbedder("text-embedding-3-small", 1024, client=client, batch_size=2)

    vectors = embedder.embed(["a", "bb", "ccc"])

    assert vectors == [[1.0], [2.0], [3.0]]
    assert [len(batch) for _, batch, _ in client.calls] == [2, 1]
    assert all(dims == 1024 for _, _, dims in client.calls)


def test_openai_provider_needs_an_api_key():
    settings = Settings(jwt_secret="x" * 32, embedding_provider="openai", embedding_api_key=None)

    with pytest.raises(ValueError, match="EMBEDDING_API_KEY"):
        get_embedder(settings, 1024)


def test_fake_provider_needs_no_api_key():
    settings = Settings(jwt_secret="x" * 32, embedding_provider="fake")

    assert isinstance(get_embedder(settings, 1024), FakeEmbedder)
