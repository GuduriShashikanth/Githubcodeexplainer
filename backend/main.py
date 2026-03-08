"""
backend/main.py
---------------
FastAPI application entry point.

Endpoints:
  GET  /health          — liveness check
  POST /analyze-repo    — index a GitHub repository
  POST /ask-question    — answer a question about an indexed repo
"""

import os
import asyncio
import time
import json
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load .env before importing services (they read env vars at import time)
load_dotenv()

from services.repo_loader import load_repository
from services.chunker     import chunk_files
from services.embeddings  import CodeEmbedder
from services.vector_store import VectorStore
from services.qa_engine   import QAEngine
from llm.groq_client      import GroqLLMClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared singletons — created once, reused across requests
# ---------------------------------------------------------------------------
# The embedding model is heavy (~130 MB) — load it once at startup.
# QAEngine instances are stored per repo_url after indexing.
_embedder: CodeEmbedder | None = None
_llm:      GroqLLMClient | None = None
repo_store: dict[str, QAEngine] = {}   # repo_url → QAEngine

MAX_CHUNKS = 1500   # safety cap — prevents OOM on free-tier cloud (512 MB RAM)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy singletons when the server starts."""
    global _embedder, _llm
    logger.info("Loading embedding model …")
    _embedder = CodeEmbedder()
    logger.info("Initialising Groq client …")
    _llm = GroqLLMClient()
    logger.info("Backend ready.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="GitHub Code Explainer API",
    description="RAG pipeline: GitHub → LangChain → FAISS → Groq",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React dev server and any production frontend
# FRONTEND_URL accepts a comma-separated list of origins, or "*" for any origin
_raw_origins = os.getenv("FRONTEND_URL", "*")
if _raw_origins == "*":
    _allowed_origins = ["*"]
else:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] + [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allowed_origins != ["*"],  # credentials not allowed with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models (Pydantic v2)
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    repo_url: str


class AnalyzeResponse(BaseModel):
    status:         str
    repo:           str
    files_indexed:  int
    chunks_created: int
    message:        str


class AskRequest(BaseModel):
    repo_url: str
    question: str


class AskResponse(BaseModel):
    answer:      str
    sources:     list[str]
    chunks_used: int
    model_used:  str


class FileTreeResponse(BaseModel):
    files: list[str]



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health():
    """Liveness check — also reports how many repos are indexed."""
    return {"status": "ok", "indexed_repos": len(repo_store)}


@app.get("/file-tree", response_model=FileTreeResponse, tags=["RAG Pipeline"])
def file_tree(repo_url: str):
    """
    Return the sorted list of all file paths indexed for a given repository.
    Used by the frontend sidebar file explorer.
    """
    engine = repo_store.get(repo_url.strip())
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=f"Repository '{repo_url}' has not been indexed yet.",
        )
    return FileTreeResponse(files=engine.all_sources)


@app.post("/analyze-repo", response_model=AnalyzeResponse, tags=["RAG Pipeline"])
async def analyze_repo(body: AnalyzeRequest):
    """
    Fetch a GitHub repository, chunk all code files, generate embeddings,
    and build a FAISS index. Stores the QAEngine in memory keyed by repo_url.

    Runs CPU-heavy work (embedding + FAISS) in a thread pool so the
    async event loop stays responsive — important on single-worker cloud deployments.
    """
    repo_url = body.repo_url.strip()
    loop     = asyncio.get_running_loop()

    # --- Step 1: fetch files ---
    t0 = time.perf_counter()
    try:
        files = await loop.run_in_executor(None, load_repository, repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error loading repo.")
        raise HTTPException(status_code=500, detail=f"Failed to load repository: {exc}")
    logger.info("[TIMER] Download:  %.2fs  (%d files)", time.perf_counter() - t0, len(files))

    # --- Step 2: chunk ---
    t1 = time.perf_counter()
    docs = await loop.run_in_executor(None, chunk_files, files)
    logger.info("[TIMER] Chunking:  %.2fs  (%d chunks)", time.perf_counter() - t1, len(docs))
    if not docs:
        raise HTTPException(
            status_code=400,
            detail="No indexable content found after chunking. The repository may be empty.",
        )

    # Cap chunks to avoid OOM on free-tier cloud (512 MB RAM)
    if len(docs) > MAX_CHUNKS:
        logger.warning(
            "Repo has %d chunks — capping to %d to avoid OOM.", len(docs), MAX_CHUNKS
        )
        docs = docs[:MAX_CHUNKS]

    # --- Step 3: embed (CPU-heavy — run in thread pool) ---
    t2 = time.perf_counter()
    try:
        embeddings = await loop.run_in_executor(
            None, lambda: _embedder.embed_documents(docs, show_progress=False)
        )
    except Exception as exc:
        logger.exception("Embedding failed.")
        raise HTTPException(status_code=500, detail=f"Embedding error: {exc}")
    logger.info("[TIMER] Embedding: %.2fs  (%d chunks → %.0f chunks/s)",
                time.perf_counter() - t2, len(docs),
                len(docs) / max(time.perf_counter() - t2, 0.01))

    # --- Step 4: build FAISS index ---
    t3 = time.perf_counter()
    store = VectorStore()
    store.build(docs, embeddings)
    logger.info("[TIMER] FAISS idx: %.2fs", time.perf_counter() - t3)

    # --- Step 5: store QAEngine ---
    engine = QAEngine(
        vector_store=store,
        embedder=_embedder,
        llm_client=_llm,
    )
    repo_store[repo_url] = engine

    # Parse owner/repo for display
    from utils.helpers import parse_github_url
    try:
        owner, repo = parse_github_url(repo_url)
        repo_label = f"{owner}/{repo}"
    except ValueError:
        repo_label = repo_url

    logger.info(
        "Indexed %s: %d files, %d chunks.", repo_label, len(files), len(docs)
    )

    return AnalyzeResponse(
        status="success",
        repo=repo_label,
        files_indexed=len(files),
        chunks_created=len(docs),
        message="Repository indexed successfully. You can now ask questions.",
    )


@app.post("/ask-question", response_model=AskResponse, tags=["RAG Pipeline"])
def ask_question(body: AskRequest):
    """
    Answer a natural-language question about a previously indexed repository.
    The repo must have been indexed via POST /analyze-repo first.
    """
    repo_url = body.repo_url.strip()
    question = body.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    engine = repo_store.get(repo_url)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Repository '{repo_url}' has not been indexed yet. "
                "Please call POST /analyze-repo first."
            ),
        )

    try:
        result = engine.answer(question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"LLM service error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error in Q&A.")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")

    return AskResponse(
        answer=result.answer,
        sources=result.sources,
        chunks_used=result.chunks_used,
        model_used=result.model_used,
    )


@app.post("/ask-question-stream", tags=["RAG Pipeline"])
async def ask_question_stream(body: AskRequest):
    """
    Stream the LLM answer token-by-token via Server-Sent Events (SSE).

    Uses an async generator + asyncio.Queue so each token is flushed to the
    client immediately — the sync Groq generator runs in a thread pool and
    pushes packets to the queue via call_soon_threadsafe.

    Events emitted:
      data: {"token": "..."}                   — one text chunk
      data: {"done": true, "sources": [...]}   — final metadata
      data: [DONE]                             — stream closed
    """
    repo_url = body.repo_url.strip()
    question = body.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    engine = repo_store.get(repo_url)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=f"Repository '{repo_url}' has not been indexed yet.",
        )

    async def event_stream():
        loop  = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        _DONE = object()   # sentinel

        def _produce():
            """Runs in a thread — pushes each packet to the async queue."""
            try:
                for packet in engine.stream_answer(question):
                    loop.call_soon_threadsafe(queue.put_nowait, packet)
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"error": str(exc)}
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _DONE)

        # Kick off the sync generator in a thread pool
        loop.run_in_executor(None, _produce)

        while True:
            item = await queue.get()
            if item is _DONE:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
