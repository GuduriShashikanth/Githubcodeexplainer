"""
backend/services/repo_loader.py
--------------------------------
Fetches source code files from a public GitHub repository.

Optimised for free-tier cloud hosting (Render, Railway, Fly.io):
  - Uses raw.githubusercontent.com instead of /contents API
    → no base64 decode, no JSON parsing, smaller payloads, faster
  - Concurrent downloads via ThreadPoolExecutor (10 workers)
  - Token auth supported on raw URLs too (same header)

Flow:
  1. Parse owner + repo from URL            (0 API calls)
  2. Detect default branch                  (1 API call)
  3. Fetch full recursive file tree         (1 API call)
  4. Filter files via should_index_file()
  5. Download raw content concurrently
  6. Return list[dict] with path + content
"""

import os
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.helpers import parse_github_url, should_index_file

logger = logging.getLogger(__name__)

API_BASE     = "https://api.github.com"
RAW_BASE     = "https://raw.githubusercontent.com"
MAX_WORKERS  = 20


def _auth_headers() -> dict:
    """Return auth headers if GITHUB_TOKEN is set, otherwise empty."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _build_api_session() -> requests.Session:
    """Session for GitHub REST API calls (tree, branch)."""
    s = requests.Session()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
        logger.info("GitHub: using token auth (5000 req/hr limit).")
    else:
        logger.warning("GITHUB_TOKEN not set — 60 req/hr limit applies.")
    s.headers.update({"Accept": "application/vnd.github+json"})
    return s


def _get_default_branch(session: requests.Session, owner: str, repo: str) -> str:
    resp = session.get(f"{API_BASE}/repos/{owner}/{repo}")
    if resp.status_code == 404:
        raise ValueError(f"Repository not found or is private: {owner}/{repo}")
    resp.raise_for_status()
    return resp.json().get("default_branch", "main")


def _get_file_tree(
    session: requests.Session, owner: str, repo: str, branch: str
) -> list[dict]:
    url  = f"{API_BASE}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = session.get(url)
    resp.raise_for_status()
    data = resp.json()
    if data.get("truncated"):
        logger.warning("Tree is truncated — repo is very large.")
    return data.get("tree", [])


def _fetch_raw(owner: str, repo: str, branch: str, path: str) -> str | None:
    """
    Fetch file content directly from raw.githubusercontent.com.

    Faster than the /contents API because:
      - Returns plain text (no JSON wrapper)
      - No base64 encoding/decoding
      - Smaller HTTP response payload
    """
    url = f"{RAW_BASE}/{owner}/{repo}/{branch}/{path}"
    try:
        resp = requests.get(url, headers=_auth_headers(), timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.warning("Failed fetching %s: %s", path, exc)
        return None


def load_repository(
    repo_url: str,
    progress_callback=None,
    max_workers: int = MAX_WORKERS,
) -> list[dict]:
    """
    Load all indexable code files from a GitHub repository.

    Cloud-optimised: uses raw content URLs + concurrent downloads.

    Args:
        repo_url:     Full GitHub URL or 'owner/repo' shorthand.
        max_workers:  Concurrent download threads (default 10).

    Returns:
        list[{"path": str, "content": str}]
    """
    owner, repo = parse_github_url(repo_url)
    logger.info("Loading repo: %s/%s", owner, repo)

    api_session = _build_api_session()
    branch      = _get_default_branch(api_session, owner, repo)
    tree        = _get_file_tree(api_session, owner, repo, branch)

    code_nodes = [
        n for n in tree
        if n["type"] == "blob" and should_index_file(n["path"], n.get("size"))
    ]

    if not code_nodes:
        raise ValueError(
            f"No indexable code files found in '{owner}/{repo}'."
        )

    total = len(code_nodes)
    logger.info(
        "Fetching %d files from raw.githubusercontent.com (%d workers) ...",
        total, max_workers,
    )

    # ── Concurrent raw content download ────────────────────────────────────
    def fetch_one(node: dict) -> tuple[str, str | None]:
        path    = node["path"]
        content = _fetch_raw(owner, repo, branch, path)
        return path, content

    completed        = 0
    path_to_content: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, n): n for n in code_nodes}
        for future in as_completed(futures):
            path, content = future.result()
            completed += 1
            if progress_callback:
                progress_callback(completed, total, path)
            if content and content.strip():
                path_to_content[path] = content

    # Restore original tree order
    files = [
        {"path": n["path"], "content": path_to_content[n["path"]]}
        for n in code_nodes
        if n["path"] in path_to_content
    ]

    logger.info("Download complete: %d/%d files.", len(files), total)
    return files
