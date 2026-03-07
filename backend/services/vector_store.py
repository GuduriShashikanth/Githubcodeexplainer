"""
backend/services/vector_store.py
----------------------------------
FAISS-based vector store: build, search, save, and load.

Index type: IndexFlatIP (Inner Product)
  - Exact nearest-neighbor search
  - Correct cosine similarity because embeddings are L2-normalised
  - Scales well for typical repository sizes (< 100k chunks)
"""

import os
import pickle
import logging
import numpy as np
import faiss
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

INDEX_FILE = "faiss.index"
DOCS_FILE  = "faiss_docs.pkl"
DEFAULT_TOP_K = 5


class VectorStore:
    """Wraps a FAISS index with the corresponding Document list."""

    def __init__(self):
        self.index: faiss.Index | None = None
        self.documents: list[Document] = []

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build(self, documents: list[Document], embeddings: np.ndarray) -> None:
        """
        Create a FAISS IndexFlatIP from pre-computed embeddings.

        Args:
            documents:  LangChain Documents — must be same order as embeddings.
            embeddings: float32 ndarray, shape (n, dim).
        """
        if len(documents) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(documents)} docs but {len(embeddings)} vectors."
            )
        if len(documents) == 0:
            raise ValueError("Cannot build an empty index.")

        n, dim = embeddings.shape
        self.documents = documents
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

        logger.info("FAISS index built: %d vectors, %d dims.", n, dim)

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def search(self, query_vec: np.ndarray, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        """
        Retrieve top-K documents most similar to the query vector.

        Returns:
            list[dict] with keys: document, score, source, snippet
        """
        if not self.is_ready:
            raise RuntimeError("VectorStore is empty. Call build() or load() first.")

        q = query_vec.reshape(1, -1).astype(np.float32)
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            doc = self.documents[idx]
            results.append({
                "document": doc,
                "score":    float(score),
                "source":   doc.metadata.get("source", "unknown"),
                "snippet":  doc.page_content[:300],
            })
        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str) -> None:
        """Persist index and docs to directory."""
        if not self.is_ready:
            raise RuntimeError("Nothing to save.")
        os.makedirs(directory, exist_ok=True)
        faiss.write_index(self.index, os.path.join(directory, INDEX_FILE))
        with open(os.path.join(directory, DOCS_FILE), "wb") as f:
            pickle.dump(self.documents, f)
        logger.info("VectorStore saved to '%s'.", directory)

    def load(self, directory: str) -> None:
        """Load a previously saved index and docs from directory."""
        ip = os.path.join(directory, INDEX_FILE)
        dp = os.path.join(directory, DOCS_FILE)
        if not (os.path.exists(ip) and os.path.exists(dp)):
            raise FileNotFoundError(f"No saved index found in '{directory}'.")
        self.index = faiss.read_index(ip)
        with open(dp, "rb") as f:
            self.documents = pickle.load(f)
        logger.info("VectorStore loaded: %d vectors.", self.index.ntotal)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self.index is not None and self.index.ntotal > 0

    @property
    def total_chunks(self) -> int:
        return self.index.ntotal if self.index else 0
