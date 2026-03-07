"""
backend/services/chunker.py
-----------------------------
Splits raw code files into overlapping chunks using LangChain's
language-aware RecursiveCharacterTextSplitter.

Language-aware splitting prefers logical boundaries (functions, classes)
before falling back to character-level splits — producing higher-quality
chunks for code retrieval.
"""

import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Extension → LangChain Language enum
EXT_TO_LANG: dict[str, Language] = {
    ".py":   Language.PYTHON,
    ".js":   Language.JS,
    ".jsx":  Language.JS,
    ".ts":   Language.JS,
    ".tsx":  Language.JS,
    ".java": Language.JAVA,
    ".cpp":  Language.CPP,
    ".c":    Language.CPP,
    ".go":   Language.GO,
    ".rb":   Language.RUBY,
    ".rs":   Language.RUST,
    ".scala":Language.SCALA,
}


def _ext(path: str) -> str:
    dot = path.rfind(".")
    return path[dot:].lower() if dot != -1 else ""


def _make_splitter(
    path: str, chunk_size: int, chunk_overlap: int
) -> RecursiveCharacterTextSplitter:
    lang = EXT_TO_LANG.get(_ext(path))
    if lang:
        return RecursiveCharacterTextSplitter.from_language(
            language=lang,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )


def chunk_files(
    files: list[dict],
    chunk_size: int = 1500,
    chunk_overlap: int = 75,
) -> list[Document]:
    """
    Convert raw file dicts into LangChain Documents.

    Args:
        files:        Output of repo_loader.load_repository().
                      Each: {"path": str, "content": str}
        chunk_size:   Max characters per chunk.
        chunk_overlap: Shared characters at chunk boundaries.

    Returns:
        list[Document] — each with metadata:
            source, extension, chunk_index, total_chunks
    """
    all_docs: list[Document] = []
    skipped = 0

    for file in files:
        path: str    = file["path"]
        content: str = file["content"]

        if not content or not content.strip():
            skipped += 1
            continue

        splitter = _make_splitter(path, chunk_size, chunk_overlap)

        try:
            chunks = splitter.split_text(content)
        except Exception as exc:
            logger.warning("Splitter error on %s: %s — skipping.", path, exc)
            skipped += 1
            continue

        # Drop trivially small chunks
        chunks = [c for c in chunks if len(c.strip()) > 20]
        total  = len(chunks)
        ext    = _ext(path)

        for i, text in enumerate(chunks):
            all_docs.append(Document(
                page_content=text,
                metadata={
                    "source":       path,
                    "extension":    ext,
                    "chunk_index":  i,
                    "total_chunks": total,
                },
            ))

    logger.info(
        "Chunking done: %d files → %d chunks (%d skipped).",
        len(files) - skipped, len(all_docs), skipped,
    )
    return all_docs
