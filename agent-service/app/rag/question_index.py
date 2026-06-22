"""
Interview question indexing and retrieval.

Provides two public functions:
    index_questions() — embed and upsert a built-in question bank into Qdrant.
    search_questions() — retrieve relevant questions via semantic + filtered search.
"""
import logging

from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

_COLLECTION = "interview_questions"

# ---------------------------------------------------------------------------
# Built-in question bank
# ---------------------------------------------------------------------------

_QUESTIONS: list[dict] = [
    # --- Behavioral / STAR ---
    {
        "id": "b001",
        "text": "Tell me about a time you had to meet a tight deadline. How did you manage it?",
        "type": "behavioral",
        "role": "general",
        "difficulty": "medium",
        "topic": "time_management",
    },
    {
        "id": "b002",
        "text": "Describe a situation where you disagreed with a teammate. How did you resolve it?",
        "type": "behavioral",
        "role": "general",
        "difficulty": "medium",
        "topic": "conflict_resolution",
    },
    {
        "id": "b003",
        "text": "Give an example of a time you had to quickly adapt to a significant change at work.",
        "type": "behavioral",
        "role": "general",
        "difficulty": "medium",
        "topic": "adaptability",
    },
    {
        "id": "b004",
        "text": "Tell me about a project you led. What was your approach and what was the outcome?",
        "type": "behavioral",
        "role": "general",
        "difficulty": "hard",
        "topic": "leadership",
    },
    {
        "id": "b005",
        "text": "Describe a time you received critical feedback. How did you respond?",
        "type": "behavioral",
        "role": "general",
        "difficulty": "medium",
        "topic": "feedback",
    },
    {
        "id": "b006",
        "text": "Tell me about a time you failed. What did you learn from the experience?",
        "type": "behavioral",
        "role": "general",
        "difficulty": "hard",
        "topic": "failure_recovery",
    },
    {
        "id": "b007",
        "text": "Describe how you handled a situation where two team members had a conflict you needed to mediate.",
        "type": "behavioral",
        "role": "general",
        "difficulty": "hard",
        "topic": "conflict_resolution",
    },
    {
        "id": "b008",
        "text": "Tell me about a time you had to collaborate with a difficult coworker to achieve a shared goal.",
        "type": "behavioral",
        "role": "general",
        "difficulty": "medium",
        "topic": "teamwork",
    },
    # --- Technical / Backend ---
    {
        "id": "t001",
        "text": "What is the difference between SQL and NoSQL databases? When would you choose each?",
        "type": "technical",
        "role": "backend",
        "difficulty": "easy",
        "topic": "databases",
    },
    {
        "id": "t002",
        "text": "Explain REST vs GraphQL. What are the trade-offs for a high-traffic API?",
        "type": "technical",
        "role": "backend",
        "difficulty": "medium",
        "topic": "api_design",
    },
    {
        "id": "t003",
        "text": "How would you design a rate limiter for a public API endpoint?",
        "type": "technical",
        "role": "backend",
        "difficulty": "hard",
        "topic": "system_design",
    },
    {
        "id": "t004",
        "text": "Describe how you would debug a slow database query in production.",
        "type": "technical",
        "role": "backend",
        "difficulty": "medium",
        "topic": "databases",
    },
    {
        "id": "t005",
        "text": "What is database indexing? How do you decide which columns to index?",
        "type": "technical",
        "role": "backend",
        "difficulty": "medium",
        "topic": "databases",
    },
    {
        "id": "t006",
        "text": "How does a message queue (e.g., Kafka or RabbitMQ) improve system resilience?",
        "type": "technical",
        "role": "backend",
        "difficulty": "hard",
        "topic": "distributed_systems",
    },
    # --- Technical / Frontend ---
    {
        "id": "f001",
        "text": "What is the virtual DOM and why does React use it?",
        "type": "technical",
        "role": "frontend",
        "difficulty": "easy",
        "topic": "react",
    },
    {
        "id": "f002",
        "text": "Explain the difference between controlled and uncontrolled components in React.",
        "type": "technical",
        "role": "frontend",
        "difficulty": "medium",
        "topic": "react",
    },
    {
        "id": "f003",
        "text": "How do you optimise a React application that is rendering too slowly?",
        "type": "technical",
        "role": "frontend",
        "difficulty": "hard",
        "topic": "performance",
    },
    # --- Technical / General Engineering ---
    {
        "id": "e001",
        "text": "What is CI/CD and what are the key stages in a typical pipeline?",
        "type": "technical",
        "role": "general",
        "difficulty": "easy",
        "topic": "devops",
    },
    {
        "id": "e002",
        "text": "Explain the CAP theorem and its implications for distributed system design.",
        "type": "technical",
        "role": "general",
        "difficulty": "hard",
        "topic": "distributed_systems",
    },
    {
        "id": "e003",
        "text": "How would you design the schema for a social-media feed with millions of users?",
        "type": "technical",
        "role": "general",
        "difficulty": "hard",
        "topic": "system_design",
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_questions(
    embedding_service: EmbeddingService | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> int:
    """
    Embed and upsert all built-in interview questions into Qdrant.

    Creates the collection if it does not exist.  Idempotent — calling it
    multiple times safely re-indexes with the same IDs (upsert semantics).

    Args:
        embedding_service: Optional pre-built instance (useful in tests).
        vector_store:       Optional pre-built instance (useful in tests).

    Returns:
        Number of questions indexed.
    """
    emb   = embedding_service or EmbeddingService()
    store = vector_store or QdrantVectorStore()

    from app.rag.embeddings import _VECTOR_DIM
    store.create_collection(_COLLECTION, vector_size=_VECTOR_DIM)

    texts   = [q["text"] for q in _QUESTIONS]
    vectors = emb.embed_batch(texts)

    items = [
        {
            "id":      q["id"],
            "vector":  vec,
            "payload": {
                "text":       q["text"],
                "type":       q["type"],
                "role":       q["role"],
                "difficulty": q["difficulty"],
                "topic":      q["topic"],
            },
        }
        for q, vec in zip(_QUESTIONS, vectors)
    ]

    store.upsert_batch(_COLLECTION, items)
    logger.info("Indexed %d interview questions into '%s'", len(items), _COLLECTION)
    return len(items)


def search_questions(
    query: str,
    role: str | None = None,
    type: str | None = None,
    difficulty: str | None = None,
    limit: int = 5,
    embedding_service: EmbeddingService | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> list[dict]:
    """
    Retrieve interview questions relevant to *query* via semantic search.

    Args:
        query:       Natural-language search query.
        role:        Optional filter — "backend", "frontend", or "general".
        type:        Optional filter — "behavioral" or "technical".
        difficulty:  Optional filter — "easy", "medium", or "hard".
        limit:       Maximum number of results to return.
        embedding_service: Optional pre-built instance (useful in tests).
        vector_store:      Optional pre-built instance (useful in tests).

    Returns:
        List of dicts, each with keys: id, score, text, type, role, difficulty, topic.
    """
    emb   = embedding_service or EmbeddingService()
    store = vector_store or QdrantVectorStore()

    query_vector = emb.embed_text(query)

    filter_conditions: dict[str, str] = {}
    if role:
        filter_conditions["role"] = role
    if type:
        filter_conditions["type"] = type
    if difficulty:
        filter_conditions["difficulty"] = difficulty

    raw = store.search(
        collection=_COLLECTION,
        query_vector=query_vector,
        limit=limit,
        filter_conditions=filter_conditions or None,
    )

    return [
        {
            "id":         r["id"],
            "score":      r["score"],
            "text":       r["payload"].get("text"),
            "type":       r["payload"].get("type"),
            "role":       r["payload"].get("role"),
            "difficulty": r["payload"].get("difficulty"),
            "topic":      r["payload"].get("topic"),
        }
        for r in raw
    ]
