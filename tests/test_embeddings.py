import math

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import Settings
from app.ingestion import (
    IngestionError,
    LocalHashEmbedder,
    SentenceTransformerEmbedder,
    build_embedder,
    ensure_collection,
)


def _cosine(left: list[float], right: list[float]) -> float:
    norm = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right, strict=True)) / norm if norm else 0.0


def test_backend_selection_is_explicit_and_defaults_to_semantic() -> None:
    assert isinstance(build_embedder(Settings()), SentenceTransformerEmbedder)
    assert isinstance(build_embedder(Settings(embedding_backend="local_hash")), LocalHashEmbedder)


def test_unknown_embedding_backend_is_rejected_by_config() -> None:
    with pytest.raises(ValueError):
        Settings(embedding_backend="magic")


async def test_hash_embedder_is_deterministic_and_correctly_shaped() -> None:
    embedder = LocalHashEmbedder(Settings(embedding_backend="local_hash", embedding_dimensions=64))

    first = await embedder.embed(["battery autonomy"])
    second = await embedder.embed(["battery autonomy"])

    assert first == second
    assert len(first[0]) == 64


async def test_semantic_embedder_rejects_a_model_dimension_mismatch(monkeypatch) -> None:
    """A model whose width disagrees with config must fail, not store bad vectors."""
    embedder = SentenceTransformerEmbedder(Settings(embedding_dimensions=384))
    monkeypatch.setattr("app.ingestion._encode", lambda _model, texts: [[0.0] * 99 for _ in texts])

    with pytest.raises(IngestionError) as caught:
        await embedder.embed(["text"])

    assert caught.value.code == "embedding_dimension_mismatch"


async def test_unloadable_model_is_a_503_and_never_falls_back_to_hashing(monkeypatch) -> None:
    """Silently substituting hash vectors would corrupt an existing collection."""

    def explode(_model, _texts):
        raise OSError("no such model")

    embedder = SentenceTransformerEmbedder(Settings())
    monkeypatch.setattr("app.ingestion._encode", explode)

    with pytest.raises(IngestionError) as caught:
        await embedder.embed(["text"])

    assert (caught.value.code, caught.value.status_code) == ("embedding_unavailable", 503)


async def test_empty_input_needs_no_model() -> None:
    assert await SentenceTransformerEmbedder(Settings()).embed([]) == []


async def test_existing_collection_with_a_different_width_is_refused() -> None:
    client = AsyncQdrantClient(location=":memory:", check_compatibility=False)
    settings = Settings(qdrant_collection="dimension_guard", embedding_dimensions=1536)
    await client.create_collection(
        collection_name="dimension_guard",
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    await ensure_collection(client, settings)  # matching width is fine

    with pytest.raises(IngestionError) as caught:
        await ensure_collection(client, settings.model_copy(update={"embedding_dimensions": 384}))

    assert caught.value.code == "embedding_dimension_mismatch"
    assert caught.value.status_code == 409
    assert "reindex" in caught.value.message


async def test_missing_collection_is_created_at_the_configured_width() -> None:
    client = AsyncQdrantClient(location=":memory:", check_compatibility=False)
    settings = Settings(qdrant_collection="fresh_collection", embedding_dimensions=384)

    await ensure_collection(client, settings)

    info = await client.get_collection("fresh_collection")
    assert info.config.params.vectors.size == 384


async def test_semantic_embedding_ranks_a_paraphrase_above_unrelated_text() -> None:
    """
    The capability the hash embedder cannot provide: matching wording that
    shares almost no tokens with the source. Skipped when the model is
    unavailable (offline CI) rather than failing.
    """
    embedder = SentenceTransformerEmbedder(Settings())
    source = "Battery autonomy: not less than 15 minutes at 100 percent rated load."
    paraphrase = "How long can the UPS run on battery power?"
    unrelated = "Switchgear enclosure shall be Type 3R for outdoor installation."

    try:
        vectors = await embedder.embed([source, paraphrase, unrelated])
    except IngestionError as exc:
        pytest.skip(f"embedding model unavailable: {exc.code}")

    assert len(vectors[0]) == 384
    assert _cosine(vectors[0], vectors[1]) > _cosine(vectors[0], vectors[2])
    assert _cosine(vectors[0], vectors[1]) > 0.3
