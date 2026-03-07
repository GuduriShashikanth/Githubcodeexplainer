"""
backend/utils/helpers.py
------------------------
URL parsing, file filtering, and path blocking utilities.
"""

import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# File extension allow-list
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".cpp", ".c", ".cs", ".go",
    ".rb", ".rs", ".php", ".swift", ".kt",
    ".scala", ".sh", ".bash",
}

# ---------------------------------------------------------------------------
# Directory block-list
# ---------------------------------------------------------------------------
IGNORED_DIRS = {
    # Build / package artefacts
    "node_modules", "dist", "build", ".git", "__pycache__",
    "venv", ".venv", "env", "vendor", "target", ".idea",
    ".vscode", "coverage", ".nyc_output", "out", "bin", "obj",
    "logs", "tmp", "temp", "cache", ".cache",
    # Tests — often 40%+ of chunks, rarely useful for code explanations
    "test", "tests", "__tests__", "spec", "specs", "__spec__",
    "e2e", "integration", "unit",
    # Docs / examples — low retrieval value
    "docs", "doc", "documentation",
    "examples", "example", "demo", "demos", "sample", "samples",
    "fixtures", "mocks", "stubs", "__mocks__",
    "migrations", "seeds",
}

# 200 KB max per file
MAX_FILE_SIZE_BYTES = 200_000


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract (owner, repo) from a GitHub URL.

    Supports:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        https://github.com/owner/repo/tree/branch/...
        owner/repo  (shorthand)

    Raises:
        ValueError: if the URL cannot be parsed as a GitHub repo.
    """
    url = url.strip().rstrip("/")

    # Shorthand: owner/repo
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", url):
        owner, repo = url.split("/")
        return owner, repo.removesuffix(".git")

    parsed = urlparse(url)
    if "github.com" not in parsed.netloc:
        raise ValueError(
            f"Not a GitHub URL: '{url}'. "
            "Expected format: https://github.com/owner/repo"
        )

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(
            f"Cannot extract owner/repo from: '{url}'. "
            "Expected format: https://github.com/owner/repo"
        )

    return parts[0], parts[1].removesuffix(".git")


def is_code_file(path: str) -> bool:
    """Return True if the file extension is in the allowed list."""
    dot = path.rfind(".")
    ext = path[dot:].lower() if dot != -1 else ""
    return ext in ALLOWED_EXTENSIONS


def is_ignored_path(path: str) -> bool:
    """Return True if any segment of the path matches the block-list."""
    parts = path.replace("\\", "/").split("/")
    return any(part in IGNORED_DIRS for part in parts)


def should_index_file(path: str, size: int | None = None) -> bool:
    """Combined check: extension + path + size."""
    if is_ignored_path(path):
        return False
    if not is_code_file(path):
        return False
    if size is not None and size > MAX_FILE_SIZE_BYTES:
        return False
    return True
