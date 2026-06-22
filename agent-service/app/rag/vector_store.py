import logging
import os
import uuid as _uuid_module

from qdrant_client import QdrantClient
from qdrant_client.http.models import SearchRequest
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 6333


class QdrantVectorStore:
    """
    Thin wrapper around the Qdrant client.

    Connection parameters are read from the environment at construction time:
        QDRANT_HOST  (default: localhost)
        QDRANT_PORT  (default: 6333)
    """

    def __init__(self) -> None:
        host = os.getenv("QDRANT_HOST", _DEFAULT_HOST)
        port = int(os.getenv("QDRANT_PORT", str(_DEFAULT_PORT)))
        # check_compatibility=False suppresses the version-mismatch warning when the
        # installed client is newer than the running Qdrant server.
        self._client = QdrantClient(host=host, port=port, check_compatibility=False)
        logger.info("QdrantVectorStore connected to %s:%d", host, port)

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(self, name: str, vector_size: int = 384) -> None:
        """Create a collection with cosine-distance vectors if it does not already exist."""
        existing = {c.name for c in self._client.get_collections().collections}
        if name in existing:
            logger.debug("Collection '%s' already exists — skipping creation", name)
            return
        self._client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Created collection '%s' (vector_size=%d)", name, vector_size)

    def delete_collection(self, name: str) -> None:
        """Delete a collection. No-ops silently if it does not exist."""
        self._client.delete_collection(collection_name=name)
        logger.info("Deleted collection '%s'", name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_id(id: "str | int") -> "int | str":
        """
        Qdrant point IDs must be either unsigned integers or UUID strings.

        Coercion rules:
          - int                → returned as-is
          - numeric string     → converted to int  (e.g. "42" → 42)
          - valid UUID string  → returned as-is    (e.g. "550e8400-...")
          - any other string   → deterministic UUID via uuid5(NAMESPACE_DNS, value)
        """
        if isinstance(id, int):
            return id
        try:
            return int(id)
        except (ValueError, TypeError):
            pass
        try:
            _uuid_module.UUID(id)
            return id  # already a valid UUID string
        except (ValueError, AttributeError):
            pass
        return str(_uuid_module.uuid5(_uuid_module.NAMESPACE_DNS, id))

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(
        self,
        collection: str,
        id: "str | int",
        vector: list[float],
        payload: dict,
    ) -> None:
        """Insert or update a single point."""
        self._client.upsert(
            collection_name=collection,
            points=[PointStruct(id=self._coerce_id(id), vector=vector, payload=payload)],
        )

    def upsert_batch(self, collection: str, items: list[dict]) -> None:
        """
        Batch insert or update.

        Each item must have the keys:
            id      — string or int identifier (see _coerce_id for rules)
            vector  — list[float] embedding vector
            payload — dict of metadata stored alongside the vector
        """
        points = [
            PointStruct(
                id=self._coerce_id(item["id"]),
                vector=item["vector"],
                payload=item["payload"],
            )
            for item in items
        ]
        self._client.upsert(collection_name=collection, points=points)
        logger.debug("Upserted %d points into '%s'", len(points), collection)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        filter_conditions: dict | None = None,
    ) -> list[dict]:
        """
        Return the top-k nearest neighbours.

        Args:
            collection:        Qdrant collection name.
            query_vector:      Query embedding vector.
            limit:             Maximum number of results to return.
            filter_conditions: Optional equality filters, e.g.
                               {"category": "behavioral", "difficulty": "medium"}.
                               All conditions are ANDed together.

        Returns:
            List of dicts, each with keys: id, score, payload.
        """
        qdrant_filter = None
        if filter_conditions:
            qdrant_filter = Filter(
                must=[
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in filter_conditions.items()
                ]
            )

        # Use the low-level search_points HTTP call so this code is compatible
        # with Qdrant server ≥ 1.0 (the high-level query_points method requires
        # server ≥ 1.10 which the currently running server may not be).
        response = self._client._client.http.search_api.search_points(
            collection_name=collection,
            search_request=SearchRequest(
                vector=query_vector,
                limit=limit,
                filter=qdrant_filter,
                with_payload=True,
            ),
        )
        return [{"id": h.id, "score": h.score, "payload": h.payload} for h in response.result]
