"""
backend/services/qa_engine.py
-------------------------------
Orchestrates the full RAG pipeline for one Q&A session.

Pipeline:
  1. Detect question intent (structure, architecture, dependency, etc.)
  2. Adjust retrieval strategy per intent
  3. embed_query(question) → query vector
  4. vector_store.search(vec, top_k) → top-K relevant chunks
  5. build_context(chunks) + scenario hint → grounded prompt context
  6. groq_client.ask/stream(question, ctx) → LLM answer
"""

import re
import logging
from dataclasses import dataclass, field
from services.embeddings import CodeEmbedder
from services.vector_store import VectorStore
from llm.groq_client import GroqLLMClient

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 8_000
DEFAULT_TOP_K     = 5


# ══════════════════════════════════════════════════════════════════════════════
# Intent Detection
# ══════════════════════════════════════════════════════════════════════════════

_STRUCTURE_KEYWORDS = [
    "file structure", "folder structure", "directory structure",
    "project structure", "codebase structure", "list files",
    "all files", "file tree", "folder tree", "what files",
    "which files", "list all", "show files", "show all files",
    "project layout", "repo structure",
]

_ARCHITECTURE_KEYWORDS = [
    "how does the project work", "architecture", "overview",
    "how is the project organized", "high level", "high-level",
    "explain the codebase", "how does this work", "what does this project do",
    "how does the app work", "how is this built", "tech stack",
    "design pattern", "main components", "how are things connected",
    "entry point", "main flow", "data flow",
]

_DEPENDENCY_KEYWORDS = [
    "import", "imports", "depend", "dependency", "dependencies",
    "what does it use", "which libraries", "packages",
    "require", "requirements", "installed packages",
]

_DEBUGGING_KEYWORDS = [
    "bug", "error", "issue", "problem", "fix", "wrong",
    "doesn't work", "does not work", "broken", "crash",
    "exception", "fail", "failing", "why does", "why is",
    "what's wrong", "what is wrong", "debug",
]

_HOWTO_KEYWORDS = [
    "how to", "how do i", "how can i", "steps to",
    "guide", "tutorial", "setup", "install", "configure",
    "run the", "start the", "deploy",
]

_COMPARISON_KEYWORDS = [
    "difference between", "compare", "vs", "versus",
    "which is better", "pros and cons", "similar to",
]

# Conversational / non-code messages that should NOT trigger RAG retrieval
_CONVERSATIONAL_PATTERNS = [
    "thank", "thanks", "thankyou", "thank you", "thx",
    "hello", "hi", "hey", "good morning", "good evening", "good afternoon",
    "bye", "goodbye", "see you", "take care",
    "ok", "okay", "got it", "understood", "makes sense",
    "great", "awesome", "perfect", "nice", "cool", "wonderful",
    "yes", "no", "yep", "nope", "sure",
    "who are you", "what are you", "what can you do",
    "help", "how does this app work",
]


def _is_conversational(question: str) -> bool:
    """Return True if the message is casual/conversational, not a code question."""
    q = question.lower().strip().rstrip("?!.")
    # Short messages that match conversational patterns
    if len(q.split()) <= 6 and any(kw in q for kw in _CONVERSATIONAL_PATTERNS):
        return True
    # Very short messages (1-2 words) are almost always conversational
    if len(q.split()) <= 2 and not _FILE_PATTERN.search(question):
        return True
    return False


class _QuestionIntent:
    """Detected intent with retrieval tuning parameters."""
    STRUCTURE     = "structure"
    ARCHITECTURE  = "architecture"
    DEPENDENCY    = "dependency"
    DEBUGGING     = "debugging"
    HOWTO         = "howto"
    COMPARISON    = "comparison"
    SPECIFIC_FILE = "specific_file"
    CONVERSATIONAL = "conversational"
    GENERAL       = "general"


# Scenario-specific hints appended to the context so the LLM
# knows *how* to frame its answer.
_SCENARIO_HINTS = {
    _QuestionIntent.ARCHITECTURE: (
        "\n\n[INSTRUCTION: This is an architecture/overview question. "
        "Provide a high-level explanation of how the components connect. "
        "Start with the entry point, describe the main modules, and explain the data flow. "
        "Use a structured breakdown with headers for each component.]\n"
    ),
    _QuestionIntent.DEPENDENCY: (
        "\n\n[INSTRUCTION: This is a dependency/import question. "
        "List all imports and external libraries found in the context. "
        "Group them by: standard library, third-party packages, and internal modules. "
        "Explain what each dependency is used for.]\n"
    ),
    _QuestionIntent.DEBUGGING: (
        "\n\n[INSTRUCTION: This is a debugging/error question. "
        "Analyze the code for potential issues. Look for: unhandled edge cases, "
        "missing error handling, type mismatches, race conditions, and incorrect logic. "
        "Suggest specific fixes with code examples where possible.]\n"
    ),
    _QuestionIntent.HOWTO: (
        "\n\n[INSTRUCTION: This is a how-to/setup question. "
        "Provide step-by-step instructions. Number each step clearly. "
        "Include exact commands, file paths, and configuration values where visible in the context.]\n"
    ),
    _QuestionIntent.COMPARISON: (
        "\n\n[INSTRUCTION: This is a comparison question. "
        "Create a clear side-by-side comparison. Use a structured format with: "
        "purpose, implementation approach, pros/cons, and when to use each.]\n"
    ),
    _QuestionIntent.SPECIFIC_FILE: (
        "\n\n[INSTRUCTION: The user is asking about a specific file. "
        "Focus your explanation on that file's purpose, its exports/public API, "
        "how it connects to the rest of the codebase, and any notable patterns or edge cases.]\n"
    ),
}

# Top-K overrides per intent (broader questions need more context)
_INTENT_TOP_K = {
    _QuestionIntent.ARCHITECTURE: 10,
    _QuestionIntent.DEPENDENCY:   8,
    _QuestionIntent.DEBUGGING:    6,
    _QuestionIntent.HOWTO:        6,
    _QuestionIntent.COMPARISON:   8,
    _QuestionIntent.SPECIFIC_FILE: 4,
    _QuestionIntent.GENERAL:      5,
}

# File extensions pattern for detecting specific file references
_FILE_PATTERN = re.compile(
    r'[\w/\\]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|css|html|json|yaml|yml|toml|md)\b',
    re.IGNORECASE,
)


def _detect_intent(question: str) -> str:
    """Classify the question to determine the best retrieval strategy."""
    q = question.lower()

    # Conversational check FIRST — before any code intent matching
    if _is_conversational(question):
        return _QuestionIntent.CONVERSATIONAL

    if any(kw in q for kw in _STRUCTURE_KEYWORDS):
        return _QuestionIntent.STRUCTURE

    if any(kw in q for kw in _ARCHITECTURE_KEYWORDS):
        return _QuestionIntent.ARCHITECTURE

    if any(kw in q for kw in _COMPARISON_KEYWORDS):
        return _QuestionIntent.COMPARISON

    if any(kw in q for kw in _DEBUGGING_KEYWORDS):
        return _QuestionIntent.DEBUGGING

    if any(kw in q for kw in _HOWTO_KEYWORDS):
        return _QuestionIntent.HOWTO

    if any(kw in q for kw in _DEPENDENCY_KEYWORDS):
        return _QuestionIntent.DEPENDENCY

    # Check if user mentioned a specific file name/path
    if _FILE_PATTERN.search(question):
        return _QuestionIntent.SPECIFIC_FILE

    return _QuestionIntent.GENERAL


# ══════════════════════════════════════════════════════════════════════════════
# QA Result
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class QAResult:
    """Structured answer returned by QAEngine.answer()."""
    answer:      str
    sources:     list[str]  = field(default_factory=list)
    chunks_used: int        = 0
    top_results: list[dict] = field(default_factory=list)
    model_used:  str        = ""
    intent:      str        = ""


# ══════════════════════════════════════════════════════════════════════════════
# QA Engine
# ══════════════════════════════════════════════════════════════════════════════

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

    # ── Main answer method ───────────────────────────────────────────────

    def answer(self, question: str) -> QAResult:
        """
        Answer a natural-language question about the indexed repository.

        Detects intent → adjusts retrieval → assembles context → calls LLM.
        """
        if not self.vector_store.is_ready:
            raise RuntimeError("Vector store is not ready. Index the repository first.")
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        intent = _detect_intent(question)
        logger.info("Question intent: %s | %s", intent, question[:100])

        # ── Conversational: no RAG needed ─────────────────────────────────
        if intent == _QuestionIntent.CONVERSATIONAL:
            return self._handle_conversational(question)

        # ── Structure questions: bypass vector search ────────────────────
        if intent == _QuestionIntent.STRUCTURE:
            return self._handle_structure(question)

        # ── Architecture questions: inject file list + broader retrieval ─
        if intent == _QuestionIntent.ARCHITECTURE:
            return self._handle_architecture(question)

        # ── All other intents: standard RAG with tuned top_k ─────────────
        top_k = _INTENT_TOP_K.get(intent, self.top_k)
        query_vec = self.embedder.embed_query(question)
        results = self.vector_store.search(query_vec, top_k=top_k)
        logger.info("Retrieved %d chunks (top_k=%d).", len(results), top_k)

        if not results:
            return QAResult(
                answer=(
                    "I could not find relevant code for your question. "
                    "Try rephrasing or ensure the repository was indexed correctly."
                ),
                intent=intent,
            )

        context, sources, chunks_used = _build_context(results, MAX_CONTEXT_CHARS)

        # Append scenario-specific hint if available
        hint = _SCENARIO_HINTS.get(intent, "")
        context += hint

        answer_text = self.llm_client.ask(question=question, context=context)

        return QAResult(
            answer=answer_text,
            sources=sources,
            chunks_used=chunks_used,
            top_results=results,
            model_used=self.llm_client.model,
            intent=intent,
        )

    # ── Streaming answer method ──────────────────────────────────────────

    def stream_answer(self, question: str):
        """
        Stream the LLM response token-by-token for a given question.

        Yields JSON-serialisable dicts:
          {"token": "..."}                  — one per LLM output chunk
          {"done": True, "sources": [...],  — final metadata packet
           "chunks_used": int, "model": str, "intent": str}
        """
        if not self.vector_store.is_ready:
            raise RuntimeError("Vector store is not ready. Index the repository first.")
        if not question.strip():
            raise ValueError("Question cannot be empty.")

        intent = _detect_intent(question)
        logger.info("[stream] Intent: %s | %s", intent, question[:100])

        # ── Conversational: instant reply ─────────────────────────────────
        if intent == _QuestionIntent.CONVERSATIONAL:
            yield from self._stream_conversational(question)
            return

        # ── Structure questions ──────────────────────────────────────────
        if intent == _QuestionIntent.STRUCTURE:
            yield from self._stream_structure(question)
            return

        # ── Architecture questions ───────────────────────────────────────
        if intent == _QuestionIntent.ARCHITECTURE:
            yield from self._stream_architecture(question)
            return

        # ── All other intents ────────────────────────────────────────────
        top_k = _INTENT_TOP_K.get(intent, self.top_k)
        query_vec = self.embedder.embed_query(question)
        results = self.vector_store.search(query_vec, top_k=top_k)

        if not results:
            yield {"token": "I could not find relevant code for your question. Try rephrasing or ask about a different part of the codebase."}
            yield {"done": True, "sources": [], "chunks_used": 0,
                   "model": self.llm_client.model, "intent": intent}
            return

        context, sources, chunks_used = _build_context(results, MAX_CONTEXT_CHARS)
        hint = _SCENARIO_HINTS.get(intent, "")
        context += hint

        logger.info("[stream] Retrieved %d chunks (top_k=%d). Streaming ...", chunks_used, top_k)

        for token in self.llm_client.stream_tokens(question=question, context=context):
            yield {"token": token}

        yield {
            "done":        True,
            "sources":     sources,
            "chunks_used": chunks_used,
            "model":       self.llm_client.model,
            "intent":      intent,
        }

    # ══════════════════════════════════════════════════════════════════════
    # Specialised handlers
    # ══════════════════════════════════════════════════════════════════════

    def _handle_conversational(self, question: str) -> QAResult:
        """Handle greetings, thanks, and casual messages without RAG."""
        response = _get_conversational_response(question)
        logger.info("Conversational message — responding without RAG.")
        return QAResult(
            answer=response,
            sources=[],
            chunks_used=0,
            model_used="none",
            intent=_QuestionIntent.CONVERSATIONAL,
        )

    def _stream_conversational(self, question: str):
        """Streaming variant for conversational messages."""
        response = _get_conversational_response(question)
        logger.info("[stream] Conversational message — instant reply.")
        yield {"token": response}
        yield {"done": True, "sources": [], "chunks_used": 0,
               "model": "none", "intent": _QuestionIntent.CONVERSATIONAL}

    def _handle_structure(self, question: str) -> QAResult:
        """Full file list injection — bypasses vector search entirely."""
        sources = self.all_sources
        context = (
            "The following is the complete list of all files indexed "
            "from this repository (one per line):\n\n"
            + "\n".join(sources)
            + "\n\n[INSTRUCTION: Present the file structure as a clean, "
            "indented directory tree. Group files by their directories. "
            "Add a brief one-line description for key files if their purpose "
            "is obvious from the name.]\n"
        )
        logger.info("Structure question — injecting %d file paths.", len(sources))
        answer_text = self.llm_client.ask(question=question, context=context)
        return QAResult(
            answer=answer_text,
            sources=sources[:20],
            chunks_used=len(sources),
            model_used=self.llm_client.model,
            intent=_QuestionIntent.STRUCTURE,
        )

    def _handle_architecture(self, question: str) -> QAResult:
        """Combine file list overview + broader chunk retrieval for architecture."""
        sources = self.all_sources
        file_overview = (
            "Complete file list for architectural context:\n"
            + "\n".join(sources) + "\n\n"
        )

        # Also retrieve semantic chunks for deeper context
        top_k = _INTENT_TOP_K[_QuestionIntent.ARCHITECTURE]
        query_vec = self.embedder.embed_query(question)
        results = self.vector_store.search(query_vec, top_k=top_k)

        chunk_context, chunk_sources, chunks_used = _build_context(
            results, MAX_CONTEXT_CHARS - len(file_overview)
        )

        context = (
            file_overview + chunk_context
            + _SCENARIO_HINTS[_QuestionIntent.ARCHITECTURE]
        )

        all_sources = list(dict.fromkeys(sources[:10] + chunk_sources))
        answer_text = self.llm_client.ask(question=question, context=context)

        return QAResult(
            answer=answer_text,
            sources=all_sources,
            chunks_used=chunks_used + len(sources),
            top_results=results,
            model_used=self.llm_client.model,
            intent=_QuestionIntent.ARCHITECTURE,
        )

    def _stream_structure(self, question: str):
        """Streaming variant of _handle_structure."""
        sources = self.all_sources
        context = (
            "The following is the complete list of all files indexed "
            "from this repository (one per line):\n\n"
            + "\n".join(sources)
            + "\n\n[INSTRUCTION: Present the file structure as a clean, "
            "indented directory tree. Group files by directories.]\n"
        )
        logger.info("[stream] Structure question — %d file paths.", len(sources))
        for token in self.llm_client.stream_tokens(question=question, context=context):
            yield {"token": token}
        yield {"done": True, "sources": sources[:20], "chunks_used": len(sources),
               "model": self.llm_client.model, "intent": _QuestionIntent.STRUCTURE}

    def _stream_architecture(self, question: str):
        """Streaming variant of _handle_architecture."""
        sources = self.all_sources
        file_overview = (
            "Complete file list for architectural context:\n"
            + "\n".join(sources) + "\n\n"
        )
        top_k = _INTENT_TOP_K[_QuestionIntent.ARCHITECTURE]
        query_vec = self.embedder.embed_query(question)
        results = self.vector_store.search(query_vec, top_k=top_k)

        chunk_context, chunk_sources, chunks_used = _build_context(
            results, MAX_CONTEXT_CHARS - len(file_overview)
        )
        context = (
            file_overview + chunk_context
            + _SCENARIO_HINTS[_QuestionIntent.ARCHITECTURE]
        )
        all_sources = list(dict.fromkeys(sources[:10] + chunk_sources))

        logger.info("[stream] Architecture question — %d paths + %d chunks.", len(sources), chunks_used)
        for token in self.llm_client.stream_tokens(question=question, context=context):
            yield {"token": token}
        yield {"done": True, "sources": all_sources,
               "chunks_used": chunks_used + len(sources),
               "model": self.llm_client.model, "intent": _QuestionIntent.ARCHITECTURE}


# ══════════════════════════════════════════════════════════════════════════════
# Conversational Response Helper
# ══════════════════════════════════════════════════════════════════════════════

def _get_conversational_response(question: str) -> str:
    """Return a friendly response for casual/conversational messages."""
    q = question.lower().strip().rstrip("?!.")

    # Thank you variants
    if any(w in q for w in ["thank", "thanks", "thankyou", "thx"]):
        return (
            "You're welcome! 😊 Feel free to ask anything else "
            "about the codebase — I'm here to help!"
        )

    # Greetings
    if any(w in q for w in ["hello", "hi", "hey", "good morning", "good evening", "good afternoon"]):
        return (
            "Hey there! 👋 I'm ready to help you explore this repository. "
            "Ask me anything about the code — how it works, what a file does, "
            "the project structure, or any specific question!"
        )

    # Farewells
    if any(w in q for w in ["bye", "goodbye", "see you", "take care"]):
        return "Goodbye! 👋 Happy coding, and feel free to come back anytime!"

    # Acknowledgements
    if any(w in q for w in ["ok", "okay", "got it", "understood", "makes sense"]):
        return (
            "Great! Let me know if you have any more questions "
            "about the codebase. 🚀"
        )

    # Positive feedback
    if any(w in q for w in ["great", "awesome", "perfect", "nice", "cool", "wonderful"]):
        return "Glad I could help! 😄 Ask away if you need anything else!"

    # Identity questions
    if any(w in q for w in ["who are you", "what are you", "what can you do"]):
        return (
            "I'm a **Code Explainer AI** 🤖 — I analyze GitHub repositories and answer "
            "your questions about the code. You can ask me about:\n\n"
            "- 📂 **File structure** — \"Show the project layout\"\n"
            "- 🏗️ **Architecture** — \"How does this project work?\"\n"
            "- 🔍 **Specific code** — \"What does auth.py do?\"\n"
            "- 🐛 **Debugging** — \"Why might this break?\"\n"
            "- 📦 **Dependencies** — \"What libraries does this use?\"\n\n"
            "Just ask in plain English!"
        )

    # Generic fallback for other conversational messages
    return (
        "I'm here to help you understand the code! "
        "Ask me any question about the repository. 😊"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Context Builder
# ══════════════════════════════════════════════════════════════════════════════

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
        header  = f"# File: {source}  (relevance: {score:.2f})\n"
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
