"""
backend/services/embeddings.py
--------------------------------
Generates dense vector embeddings using BAAI/bge-small-en
from the sentence-transformers library.

Model: BAAI/bge-small-en
  - 384 dimensions
  - ~130 MB download, cached locally on first run
  - Free and runs entirely locally (no API calls)
  - Top-ranked on MTEB leaderboard for retrieval tasks
  - BGE models require a special query prefix for best results
"""

import logging
import numpy as np
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en"

# BGE models achieve best retrieval performance when the query
# is prefixed with this instruction string.
# Document embeddings do NOT use the prefix.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class CodeEmbedder:
    """
    Wraps sentence-transformers for generating L2-normalised embeddings.
    """

    def __init__(self, model_name: str = MODEL_NAME, device: str = "cpu"):
        logger.info("Loading embedding model: %s …", model_name)
        self.model      = SentenceTransformer(model_name, device=device)
        self.model_name = model_name
        self.dim        = self.model.get_sentence_embedding_dimension()
        logger.info("Model ready. Dim: %d", self.dim)

    def embed_documents(
        self,
        documents: list[Document],
        batch_size: int = 128,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode a list of Documents into a float32 matrix.

        Returns:
            np.ndarray of shape (n, dim), dtype=float32, L2-normalised.
        """
        if not documents:
            return np.empty((0, self.dim), dtype=np.float32)

        texts = [doc.page_content for doc in documents]
        logger.info("Embedding %d chunks …", len(texts))

        vecs = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-normalise for cosine via dot product
        )
        return vecs.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Encode a user question into a 1-D float32 vector.
        BGE models use a query prefix for better retrieval quality.
        """
        prefixed = BGE_QUERY_PREFIX + query
        vec = self.model.encode(
            prefixed,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vec.astype(np.float32)

    @property
    def embedding_dim(self) -> int:
        return self.dim
