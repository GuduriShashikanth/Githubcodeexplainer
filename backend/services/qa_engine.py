"""
backend/services/qa_engine.py
-------------------------------
Orchestrates the full RAG pipeline for one Q&A session.

Pipeline:
  1. embed_query(question)          → query vector
  2. vector_store.search(vec, top_k) → top-K relevant chunks
  3. build_context(chunks)           → grounded prompt context
  4. groq_client.ask(question, ctx)  → LLM answer
"""

import logging
from dataclasses import dataclass, field
from services.embeddings import CodeEmbedder
from services.vector_store import VectorStore
from llm.groq_client import GroqLLMClient

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 6_000
DEFAULT_TOP_K     = 5

# Keywords that indicate the user wants to know about file/folder structure
_STRUCTURE_KEYWORDS = [
    "file structure", "folder structure", "directory structure",
    "project structure", "codebase structure", "list files",
    "all files", "file tree", "folder tree", "what files",
    "which files", "list all", "show files", "show all files",
]

def _is_structure_question(question: str) -> bool:
    """Return True if the question is asking about the project's file layout."""
    q = question.lower()
    return any(kw in q for kw in _STRUCTURE_KEYWORDS)


@dataclass
class QAResult:
    """Structured answer returned by QAEngine.answer()."""
    answer:      str
    sources:     list[str]  = field(default_factory=list)
    chunks_used: int        = 0
    top_results: list[dict] = field(default_factory=list)
    model_used:  str        = ""


class QAEngine:
    """
    Coordinates embedding, retrieval, and LLM generation.

    One QAEngine instance per indexed repository — stored in FastAPI's
    in-memory repo_store dict.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: CodeEmbedder,
        llm_client: GroqLLMClient,
        top_k: int = DEFAULT_TOP_K,
    ):
        self.vector_store = vector_store
        self.embedder     = embedder
        self.llm_client   = llm_client
        self.top_k        = top_k

    @property
    def all_sources(self) -> list[str]:
        """Return a sorted list of every unique file path in the index."""
        seen: set[str] = set()
        for doc in self.vector_store.documents:
            src = doc.metadata.get("source", "")
            if src:
                seen.add(src)
        return sorted(seen)

    def answer(self, question: str) -> QAResult:
        """
        Answer a natural-language question about the indexed repository.

        Args:
            question: User's question string.

        Returns:
            QAResult with answer text, source files, and chunk count.
        """
        if not self.vector_store.is_ready:
            raise RuntimeError(
                "Vector store is not ready. Index the repository first."
            )
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        logger.info("Processing question: %s", question[:100])

        # ── Special case: file structure question ────────────────────────
        if _is_structure_question(question):
            sources = self.all_sources
            context = (
                "The following is the complete list of all files indexed "
                "from this repository (one per line):\n\n"
                + "\n".join(sources)
            )
            logger.info("Structure question detected — injecting %d file paths.", len(sources))
            answer_text = self.llm_client.ask(question=question, context=context)
            return QAResult(
                answer=answer_text,
                sources=sources[:20],
                chunks_used=len(sources),
                model_used=self.llm_client.model,
            )

        logger.info("Processing question: %s", question[:100])

        # Step 1 — embed question (with BGE prefix applied inside embed_query)
        query_vec = self.embedder.embed_query(question)

        # Step 2 — retrieve relevant code chunks
        results = self.vector_store.search(query_vec, top_k=self.top_k)
        logger.info("Retrieved %d chunks.", len(results))

        if not results:
            return QAResult(
                answer=(
                    "I could not find relevant code for your question. "
                    "Try rephrasing or ensure the repository was indexed correctly."
                )
            )

        # Step 3 — assemble context string
        context, sources, chunks_used = _build_context(results, MAX_CONTEXT_CHARS)

        # Step 4 — call Groq LLM
        answer_text = self.llm_client.ask(question=question, context=context)

        return QAResult(
            answer=answer_text,
            sources=sources,
            chunks_used=chunks_used,
            top_results=results,
            model_used=self.llm_client.model,
        )

    def stream_answer(self, question: str):
        """
        Stream the LLM response token-by-token for a given question.

        Yields JSON-serialisable dicts:
          {"token": "..."}               — one per LLM output chunk
          {"done": True, "sources": [...],  — final metadata packet
           "chunks_used": int,
           "model": str}
        """
        if not self.vector_store.is_ready:
            raise RuntimeError("Vector store is not ready. Index the repository first.")
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        logger.info("[stream] Processing question: %s", question[:100])

        # ── Special case: file structure question ────────────────────────
        if _is_structure_question(question):
            sources = self.all_sources
            context = (
                "The following is the complete list of all files indexed "
                "from this repository (one per line):\n\n"
                + "\n".join(sources)
            )
            logger.info("[stream] Structure question — injecting %d file paths.", len(sources))
            for token in self.llm_client.stream_tokens(question=question, context=context):
                yield {"token": token}
            yield {"done": True, "sources": sources[:20], "chunks_used": len(sources),
                   "model": self.llm_client.model}
            return

        query_vec = self.embedder.embed_query(question)
        results   = self.vector_store.search(query_vec, top_k=self.top_k)

        if not results:
            yield {"token": "I could not find relevant code for your question. Try rephrasing or ask about a different part of the codebase."}
            yield {"done": True, "sources": [], "chunks_used": 0, "model": self.llm_client.model}
            return

        context, sources, chunks_used = _build_context(results, MAX_CONTEXT_CHARS)
        logger.info("[stream] Retrieved %d chunks. Starting token stream ...", chunks_used)

        for token in self.llm_client.stream_tokens(question=question, context=context):
            yield {"token": token}

        yield {
            "done":       True,
            "sources":    sources,
            "chunks_used": chunks_used,
            "model":      self.llm_client.model,
        }


def _build_context(
    results: list[dict],
    max_chars: int,
) -> tuple[str, list[str], int]:
    """
    Concatenate retrieved chunks into a single context string.
    Truncates to max_chars to stay inside the LLM context window.
    """
    parts:   list[str] = []
    sources: list[str] = []
    total   = 0
    used    = 0

    for r in results:
        source  = r["source"]
        score   = r["score"]
        text    = r["document"].page_content
        header  = f"# File: {source}  (score: {score:.2f})\n"
        block   = header + text + "\n\n---\n\n"

        if total + len(block) > max_chars:
            remaining = max_chars - total - len(header) - 10
            if remaining > 100:
                parts.append(header + text[:remaining] + "\n… [truncated]\n\n---\n\n")
                used += 1
            break

        parts.append(block)
        total += len(block)
        used  += 1
        if source not in sources:
            sources.append(source)

    return "".join(parts), sources, used
