import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_VECTOR_DIM = 384


class EmbeddingService:
    """
    Sentence-transformer embedding service.

    The underlying model is lazy-loaded on the first call to embed_text() or
    embed_batch(), so importing this module does not trigger a model download or
    GPU initialisation.
    """

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name
        self._model: Optional[object] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """Return the embedding vector for a single text string."""
        return self._model_instance().encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a list of text strings."""
        return [v.tolist() for v in self._model_instance().encode(texts)]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _model_instance(self):
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self):
        from sentence_transformers import SentenceTransformer

        t0 = time.perf_counter()
        model = SentenceTransformer(self._model_name)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info("Loaded embedding model '%s' in %d ms", self._model_name, elapsed_ms)
        return model
