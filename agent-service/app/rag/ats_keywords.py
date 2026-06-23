"""
ATS keyword library organised by industry → role → keywords.

Public API
----------
index_ats_keywords()             — embed and upsert all keywords into Qdrant.
get_ats_keywords_for_role()      — look up the keyword list for an industry/role pair.
find_missing_keywords()          — compare a resume text against the role keyword list.
"""
import logging

from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)

_COLLECTION = "ats_keywords"

# ---------------------------------------------------------------------------
# Keyword library
# ---------------------------------------------------------------------------

_ATS_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "technology": {
        "backend_engineer": [
            "Java", "Python", "Spring Boot", "REST API", "microservices",
            "PostgreSQL", "MySQL", "Redis", "Kafka", "Docker", "Kubernetes",
            "CI/CD", "Git", "Agile", "unit testing", "integration testing",
            "system design", "scalability", "load balancing", "message queue",
            "ORM", "JPA", "Hibernate", "Maven", "Gradle",
        ],
        "frontend_developer": [
            "React", "TypeScript", "JavaScript", "HTML", "CSS", "Redux",
            "Next.js", "Vue.js", "Angular", "Webpack", "Vite",
            "responsive design", "accessibility", "SEO", "REST API",
            "GraphQL", "state management", "component design",
            "performance optimization", "cross-browser",
        ],
        "data_scientist": [
            "Python", "R", "SQL", "machine learning", "deep learning",
            "TensorFlow", "PyTorch", "scikit-learn", "pandas", "numpy",
            "data visualization", "statistical analysis", "NLP",
            "computer vision", "A/B testing", "feature engineering",
            "model deployment", "ETL", "Spark", "Hadoop",
        ],
        "devops_engineer": [
            "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
            "Ansible", "Jenkins", "GitHub Actions", "CI/CD", "Linux",
            "monitoring", "Prometheus", "Grafana", "ELK stack",
            "infrastructure as code", "networking", "security",
            "load balancing", "auto-scaling",
        ],
        "fullstack_developer": [
            "React", "Node.js", "TypeScript", "Python", "PostgreSQL",
            "MongoDB", "REST API", "GraphQL", "Docker", "Git", "Agile",
            "responsive design", "authentication", "authorization",
            "testing", "deployment", "AWS", "microservices",
        ],
    },
    "finance": {
        "quantitative_analyst": [
            "Python", "C++", "R", "SQL", "stochastic calculus",
            "time series", "Monte Carlo", "risk modeling", "derivatives",
            "Bloomberg", "VBA", "statistical arbitrage",
        ],
    },
    "healthcare": {
        "health_informatics": [
            "HL7", "FHIR", "EHR", "HIPAA", "Python", "SQL",
            "data analytics", "clinical workflows", "interoperability",
            "medical coding",
        ],
    },
}

# ---------------------------------------------------------------------------
# Simple keyword categorisation
# ---------------------------------------------------------------------------

_LANGUAGES = {
    "java", "python", "c++", "r", "sql", "javascript", "typescript",
    "html", "css", "vba",
}
_FRAMEWORKS = {
    "spring boot", "react", "redux", "next.js", "vue.js", "angular",
    "node.js", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "spark", "hadoop", "django", "fastapi",
}
_TOOLS = {
    "docker", "kubernetes", "kafka", "redis", "git", "maven", "gradle",
    "webpack", "vite", "terraform", "ansible", "jenkins", "github actions",
    "prometheus", "grafana", "bloomberg", "postgresql", "mysql", "mongodb",
    "aws", "azure", "gcp", "linux",
}


def _categorise(keyword: str) -> str:
    """Return a coarse category tag for a keyword."""
    kw = keyword.lower()
    if kw in _LANGUAGES:
        return "language"
    if kw in _FRAMEWORKS:
        return "framework"
    if kw in _TOOLS:
        return "tool"
    return "concept"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_ats_keywords(
    embedding_service: EmbeddingService | None = None,
    vector_store: QdrantVectorStore | None = None,
) -> int:
    """
    Embed and upsert all ATS keywords into Qdrant.

    Each keyword becomes one point whose payload carries:
        keyword   — the raw keyword string
        industry  — e.g. "technology"
        role      — e.g. "backend_engineer"
        category  — "language" | "framework" | "tool" | "concept"

    The collection is created if it does not already exist.  Calling this
    function multiple times is safe (upsert semantics on stable IDs).

    Returns:
        Total number of keywords indexed.
    """
    from app.rag.embeddings import _VECTOR_DIM

    emb   = embedding_service or EmbeddingService()
    store = vector_store or QdrantVectorStore()

    store.create_collection(_COLLECTION, vector_size=_VECTOR_DIM)

    # Flatten the library into a list of records with stable IDs
    records: list[dict] = []
    for industry, roles in _ATS_KEYWORDS.items():
        for role, keywords in roles.items():
            for i, keyword in enumerate(keywords):
                records.append({
                    "id":       f"{industry}_{role}_{i}",
                    "keyword":  keyword,
                    "industry": industry,
                    "role":     role,
                    "category": _categorise(keyword),
                })

    texts   = [r["keyword"] for r in records]
    vectors = emb.embed_batch(texts)

    items = [
        {
            "id":      record["id"],
            "vector":  vec,
            "payload": {
                "keyword":  record["keyword"],
                "industry": record["industry"],
                "role":     record["role"],
                "category": record["category"],
            },
        }
        for record, vec in zip(records, vectors)
    ]

    store.upsert_batch(_COLLECTION, items)
    logger.info("Indexed %d ATS keywords into '%s'", len(items), _COLLECTION)
    return len(items)


def get_ats_keywords_for_role(industry: str, role: str) -> list[str]:
    """
    Return the keyword list for a specific industry / role combination.

    Args:
        industry: Top-level industry key, e.g. "technology".
        role:     Role key within that industry, e.g. "backend_engineer".

    Returns:
        List of keyword strings, or an empty list if the combination is unknown.
    """
    return _ATS_KEYWORDS.get(industry, {}).get(role, [])


def find_missing_keywords(
    resume_text: str,
    industry: str,
    role: str,
) -> dict:
    """
    Compare a resume's raw text against the ATS keyword list for the given role.

    Matching is case-insensitive substring search: a keyword is considered
    "present" if it appears anywhere in the resume text.

    Args:
        resume_text: Raw text extracted from the candidate's resume.
        industry:    Industry key, e.g. "technology".
        role:        Role key, e.g. "backend_engineer".

    Returns:
        {
            "present":          list[str],   # keywords found in resume_text
            "missing":          list[str],   # keywords not found
            "coverage_percent": float,       # 0.0–100.0
        }
        If the industry/role combination is unknown, all three fields reflect
        an empty keyword list (coverage = 100.0 by convention).
    """
    keywords = get_ats_keywords_for_role(industry, role)

    if not keywords:
        logger.warning(
            "No ATS keywords found for industry=%r role=%r", industry, role
        )
        return {"present": [], "missing": [], "coverage_percent": 100.0}

    text_lower = resume_text.lower()
    present: list[str] = []
    missing: list[str] = []

    for kw in keywords:
        if kw.lower() in text_lower:
            present.append(kw)
        else:
            missing.append(kw)

    coverage = round(len(present) / len(keywords) * 100.0, 1)

    return {
        "present":          present,
        "missing":          missing,
        "coverage_percent": coverage,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stdout,
    )

    print("Indexing ATS keywords into Qdrant…")
    count = index_ats_keywords()
    print(f"Done — {count} keywords indexed into '{_COLLECTION}'.")

    # Quick smoke-test: look up one role
    sample = get_ats_keywords_for_role("technology", "backend_engineer")
    print(f"\nSample — technology/backend_engineer ({len(sample)} keywords):")
    print("  " + ", ".join(sample[:8]) + ", …")
