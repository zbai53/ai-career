"""
Tests for EmbeddingService and QdrantVectorStore.

Embedding tests run without any external service.
The Qdrant test is skipped automatically when Qdrant is not reachable on
localhost:6333 so it passes cleanly in CI without Docker.
"""

import uuid

import pytest

from app.rag.embeddings import EmbeddingService, _VECTOR_DIM

# ---------------------------------------------------------------------------
# Shared fixture — one EmbeddingService instance per module (model loads once)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def embedding_service() -> EmbeddingService:
    return EmbeddingService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _qdrant_reachable() -> bool:
    """Return True if Qdrant is accepting connections on localhost:6333."""
    try:
        from qdrant_client import QdrantClient
        QdrantClient(host="localhost", port=6333).get_collections()
        return True
    except Exception:
        return False


_qdrant_available = pytest.mark.skipif(
    not _qdrant_reachable(),
    reason="Qdrant not reachable on localhost:6333 — start Docker to run this test",
)

# ---------------------------------------------------------------------------
# EmbeddingService tests
# ---------------------------------------------------------------------------

class TestEmbedText:
    def test_embed_text_returns_vector(self, embedding_service: EmbeddingService) -> None:
        """embed_text must return a list of exactly _VECTOR_DIM floats."""
        vector = embedding_service.embed_text("Implemented REST APIs using Python and FastAPI")

        assert isinstance(vector, list), "embed_text must return a list"
        assert len(vector) == _VECTOR_DIM, (
            f"Expected {_VECTOR_DIM} dimensions, got {len(vector)}"
        )
        assert all(isinstance(v, float) for v in vector), "All elements must be floats"

    def test_embed_text_empty_string(self, embedding_service: EmbeddingService) -> None:
        """embed_text must handle an empty string without raising."""
        vector = embedding_service.embed_text("")
        assert len(vector) == _VECTOR_DIM

    def test_embed_text_different_inputs_differ(self, embedding_service: EmbeddingService) -> None:
        """Two distinct sentences must produce different embedding vectors."""
        v1 = embedding_service.embed_text("Software engineer with Python experience")
        v2 = embedding_service.embed_text("Marketing manager with SEO expertise")
        assert v1 != v2, "Semantically different texts must have different embeddings"


class TestEmbedBatch:
    def test_embed_batch_returns_correct_count(self, embedding_service: EmbeddingService) -> None:
        """embed_batch must return exactly one vector per input text."""
        texts = [
            "Built scalable REST APIs using Django",
            "Managed PostgreSQL databases and wrote complex queries",
            "Led cross-functional team of 5 engineers",
        ]
        vectors = embedding_service.embed_batch(texts)

        assert len(vectors) == len(texts), (
            f"Expected {len(texts)} vectors, got {len(vectors)}"
        )
        for i, vector in enumerate(vectors):
            assert len(vector) == _VECTOR_DIM, (
                f"Vector {i} has {len(vector)} dims, expected {_VECTOR_DIM}"
            )
            assert all(isinstance(v, float) for v in vector), (
                f"Vector {i} contains non-float values"
            )

    def test_embed_batch_single_item_matches_embed_text(
        self, embedding_service: EmbeddingService
    ) -> None:
        """A single-item batch must produce the same vector as embed_text."""
        text = "Designed microservices architecture on AWS"
        single = embedding_service.embed_text(text)
        batch  = embedding_service.embed_batch([text])

        assert len(batch) == 1
        # Compare element-wise with tolerance for float precision
        assert all(
            abs(a - b) < 1e-6 for a, b in zip(single, batch[0])
        ), "embed_text and embed_batch([text]) must return the same vector"


# ---------------------------------------------------------------------------
# QdrantVectorStore tests (require live Qdrant)
# ---------------------------------------------------------------------------

@_qdrant_available
class TestQdrantCreateAndSearch:
    """Integration tests — run only when Qdrant is reachable."""

    def test_qdrant_create_and_search(self, embedding_service: EmbeddingService) -> None:
        """
        Full round-trip: create collection → upsert 3 items → search → assert
        top result is the closest match → delete collection.
        """
        from app.rag.vector_store import QdrantVectorStore

        store = QdrantVectorStore()
        collection = f"test-rag-{uuid.uuid4().hex[:8]}"

        # Corpus: three semantically distinct resume bullets
        documents = [
            {
                "id":   "1",
                "text": "Engineered scalable REST APIs using Python and FastAPI",
                "tag":  "backend",
            },
            {
                "id":   "2",
                "text": "Managed PostgreSQL databases and optimised slow queries",
                "tag":  "database",
            },
            {
                "id":   "3",
                "text": "Led Agile sprint planning and stakeholder ceremonies",
                "tag":  "management",
            },
        ]

        try:
            store.create_collection(collection, vector_size=_VECTOR_DIM)

            # Upsert via batch
            store.upsert_batch(
                collection,
                [
                    {
                        "id":      doc["id"],
                        "vector":  embedding_service.embed_text(doc["text"]),
                        "payload": {"text": doc["text"], "tag": doc["tag"]},
                    }
                    for doc in documents
                ],
            )

            # Query: semantically closest to document 1 (backend API work)
            query_vector = embedding_service.embed_text(
                "Developed backend services and HTTP endpoints"
            )
            results = store.search(collection, query_vector, limit=3)

            assert len(results) > 0, "search must return at least one result"

            # The top result must be the backend API bullet (id="1" coerced to int 1)
            top = results[0]
            assert top["id"] == 1, (
                f"Expected top result id=1 (backend/API), got '{top['id']}' "
                f"(payload={top['payload']})"
            )
            assert 0.0 <= top["score"] <= 1.0, (
                f"Cosine similarity score must be in [0, 1], got {top['score']}"
            )
            assert top["payload"]["tag"] == "backend"

        finally:
            # Always clean up — even if assertions fail
            store.delete_collection(collection)

    def test_qdrant_single_upsert_and_retrieve(
        self, embedding_service: EmbeddingService
    ) -> None:
        """upsert() (single point) must be findable via search."""
        from app.rag.vector_store import QdrantVectorStore

        store = QdrantVectorStore()
        collection = f"test-single-{uuid.uuid4().hex[:8]}"

        try:
            store.create_collection(collection, vector_size=_VECTOR_DIM)

            text = "Implemented CI/CD pipelines using GitHub Actions and Docker"
            store.upsert(
                collection,
                id="point-1",
                vector=embedding_service.embed_text(text),
                payload={"text": text, "category": "devops"},
            )

            results = store.search(
                collection,
                embedding_service.embed_text("automated deployment pipeline"),
                limit=1,
            )

            assert len(results) == 1
            # "point-1" is not numeric/UUID so _coerce_id converts it to a uuid5 UUID string
            assert results[0]["payload"]["category"] == "devops"

        finally:
            store.delete_collection(collection)

    def test_qdrant_filter_conditions(self, embedding_service: EmbeddingService) -> None:
        """search with filter_conditions must restrict results to matching payload fields."""
        from app.rag.vector_store import QdrantVectorStore

        store = QdrantVectorStore()
        collection = f"test-filter-{uuid.uuid4().hex[:8]}"

        items = [
            {"id": "a", "text": "Python backend development", "category": "backend"},
            {"id": "b", "text": "React frontend components",   "category": "frontend"},
            {"id": "c", "text": "Django REST framework APIs",  "category": "backend"},
        ]

        try:
            store.create_collection(collection, vector_size=_VECTOR_DIM)
            store.upsert_batch(
                collection,
                [
                    {
                        "id":      item["id"],
                        "vector":  embedding_service.embed_text(item["text"]),
                        "payload": {"text": item["text"], "category": item["category"]},
                    }
                    for item in items
                ],
            )

            # Search with category filter — must only return backend results
            results = store.search(
                collection,
                embedding_service.embed_text("server-side API development"),
                limit=3,
                filter_conditions={"category": "backend"},
            )

            assert len(results) >= 1, "Filtered search must return at least one backend result"
            for r in results:
                assert r["payload"]["category"] == "backend", (
                    f"filter_conditions not applied — got category='{r['payload']['category']}'"
                )

        finally:
            store.delete_collection(collection)


# ---------------------------------------------------------------------------
# Question index tests (require live Qdrant)
# ---------------------------------------------------------------------------

@_qdrant_available
class TestQuestionIndex:
    """Integration tests for index_questions() and search_questions()."""

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self, embedding_service: EmbeddingService) -> None:
        """Index questions once per class; clean up the collection after."""
        from app.rag.vector_store import QdrantVectorStore
        from app.rag.question_index import index_questions, _COLLECTION

        self._store = QdrantVectorStore()
        self._emb = embedding_service

        index_questions(
            embedding_service=embedding_service,
            vector_store=self._store,
        )
        yield
        # Teardown — remove the collection so tests stay idempotent
        self._store.delete_collection(_COLLECTION)

    def test_search_questions_by_role(self, embedding_service: EmbeddingService) -> None:
        """
        Filtering by role="backend" must return only backend questions.
        """
        from app.rag.question_index import search_questions

        results = search_questions(
            query="server-side API design and databases",
            role="backend",
            limit=5,
            embedding_service=embedding_service,
            vector_store=self._store,
        )

        assert len(results) >= 1, "Should return at least one backend question"
        for r in results:
            assert r["role"] == "backend", (
                f"role filter not applied — got role='{r['role']}' for: {r['text'][:60]}"
            )
        # Scores must be valid cosine similarities
        for r in results:
            assert 0.0 <= r["score"] <= 1.0, f"score {r['score']} out of [0, 1]"

    def test_search_questions_by_type(self, embedding_service: EmbeddingService) -> None:
        """
        Filtering by type="behavioral" must return only behavioral questions.
        """
        from app.rag.question_index import search_questions

        results = search_questions(
            query="working with teammates and handling pressure",
            type="behavioral",
            limit=5,
            embedding_service=embedding_service,
            vector_store=self._store,
        )

        assert len(results) >= 1, "Should return at least one behavioral question"
        for r in results:
            assert r["type"] == "behavioral", (
                f"type filter not applied — got type='{r['type']}' for: {r['text'][:60]}"
            )

    def test_search_semantic_match(self, embedding_service: EmbeddingService) -> None:
        """
        Semantic search for a conflict/teamwork query must rank a conflict or
        teamwork question in the top-2 results (no filter applied).
        """
        from app.rag.question_index import search_questions

        results = search_questions(
            query="how to handle disagreements with coworkers",
            limit=3,
            embedding_service=embedding_service,
            vector_store=self._store,
        )

        assert len(results) >= 1, "Semantic search must return at least one result"

        conflict_teamwork_topics = {"conflict_resolution", "teamwork"}
        top2_topics = {r["topic"] for r in results[:2]}

        assert top2_topics & conflict_teamwork_topics, (
            f"Expected a conflict/teamwork question in top-2, got topics: {top2_topics}\n"
            f"Top results: {[r['text'][:60] for r in results[:2]]}"
        )
