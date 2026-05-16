"""GitHub-backed import helpers for public rules, skills, and tools."""
from __future__ import annotations

import json
import os
from pathlib import PurePosixPath
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import frontmatter
import yaml

GITHUB_API_BASE = "https://api.github.com"
_IMPORTABLE_EXTENSIONS = (".md", ".markdown", ".json", ".yaml", ".yml")
_GITHUB_TOKEN_ENV = "GITHUB_TOKEN"

# Stems of generic documentation files that should never be treated as skill or
# rule definitions, even if they happen to live inside a /skills/ or /rules/
# directory.
_GENERIC_DOC_STEMS: frozenset[str] = frozenset({
    "readme", "changelog", "contributing", "license", "index", "overview",
})


def search_repositories_page(query: str, limit: int = 8, page: int = 1) -> dict:
    """Search public GitHub repositories that may contain shareable knowledge assets."""
    normalized_query = query.strip()
    if not normalized_query:
        return {"items": [], "total_count": 0, "page": page, "per_page": limit}

    payload = _github_get_json(
        f"{GITHUB_API_BASE}/search/repositories?q={quote_plus(normalized_query)}&sort=stars&per_page={limit}&page={page}"
    )
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return {
        "items": [
            {
                "full_name": item.get("full_name", ""),
                "description": item.get("description") or "",
                "html_url": item.get("html_url", ""),
                "default_branch": item.get("default_branch") or "main",
                "stargazers_count": int(item.get("stargazers_count") or 0),
                "language": item.get("language") or "",
            }
            for item in items
            if item.get("full_name")
        ],
        "total_count": int(payload.get("total_count") or 0),
        "page": page,
        "per_page": limit,
    }


def search_repositories(query: str, limit: int = 8) -> list[dict]:
    """Backward-compatible first page of GitHub repository search results."""
    return search_repositories_page(query, limit=limit, page=1)["items"]


def list_import_candidates(
    repo_full_name: str,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Return importable rule, skill, and tool files from a public GitHub repository."""
    repo = _get_repo_metadata(repo_full_name)
    tree_payload = _github_get_json(
        f"{GITHUB_API_BASE}/repos/{repo_full_name}/git/trees/{repo['default_branch']}?recursive=1"
    )
    tree = tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
    return select_import_candidates(tree, repo_full_name, repo["default_branch"], query=query, kind=kind, limit=limit)


def select_import_candidates(
    tree: list[dict],
    repo_full_name: str,
    default_branch: str,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Select and rank importable files from a Git tree payload."""
    needle = (query or "").strip().lower()
    normalized_kind = None if not kind or kind == "all" else kind
    candidates: list[dict] = []

    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "")
        candidate_kind = infer_candidate_type(path)
        if candidate_kind is None:
            continue
        if normalized_kind and candidate_kind != normalized_kind:
            continue
        if needle and needle not in path.lower():
            continue

        score = _candidate_score(path, candidate_kind, needle)
        candidates.append(
            {
                "name": PurePosixPath(path).name,
                "path": path,
                "type": candidate_kind,
                "raw_url": _raw_content_url(repo_full_name, default_branch, path),
                "html_url": f"https://github.com/{repo_full_name}/blob/{default_branch}/{path}",
                "score": score,
            }
        )

    ranked = sorted(candidates, key=lambda candidate: (-candidate["score"], candidate["path"]))
    return [{k: v for k, v in candidate.items() if k != "score"} for candidate in ranked[:limit]]


def infer_candidate_type(path: str) -> Optional[str]:
    """Infer whether a repo file is best treated as a skill, rule, or tool.

    Generic documentation files (README, CHANGELOG, etc.) are excluded from
    skill and rule classification even when they reside inside a skills/ or
    rules/ directory, because they are unlikely to be properly formatted skill
    or rule definitions.
    """
    lowered = path.lower()
    if not lowered.endswith(_IMPORTABLE_EXTENSIONS):
        return None

    stem = PurePosixPath(lowered).stem

    if lowered.endswith("skill.md") or "/skills/" in lowered or "/skill/" in lowered:
        if stem in _GENERIC_DOC_STEMS:
            return None
        return "skill"
    if lowered.endswith(".instructions.md") or "/rules/" in lowered or "/rule/" in lowered:
        if stem in _GENERIC_DOC_STEMS:
            return None
        return "rule"
    if "/tools/" in lowered or "/tool/" in lowered or lowered.endswith((".json", ".yaml", ".yml")):
        return "tool"
    return None


def fetch_import_document(repo_full_name: str, path: str) -> dict:
    """Fetch and parse a single GitHub file for import into the shared brain."""
    repo = _get_repo_metadata(repo_full_name)
    raw_url = _raw_content_url(repo_full_name, repo["default_branch"], path)
    content = _github_get_text(raw_url)
    inferred_type = infer_candidate_type(path) or "document"
    return parse_import_document(repo_full_name, repo["default_branch"], path, content, inferred_type)


def parse_import_document(
    repo_full_name: str,
    default_branch: str,
    path: str,
    content: str,
    inferred_type: str,
) -> dict:
    """Normalize remote GitHub content into a Shared Synapse document payload."""
    source_url = f"https://github.com/{repo_full_name}/blob/{default_branch}/{path}"
    source_metadata = {
        "source_repo": repo_full_name,
        "source_path": path,
        "source_url": source_url,
        "source_branch": default_branch,
        "imported_via": "github",
    }
    lowered = path.lower()
    default_id = _slugify_name(PurePosixPath(path).stem)

    if lowered.endswith((".md", ".markdown")):
        post = frontmatter.loads(content)
        metadata = dict(post.metadata)
        document_id = _slugify_name(str(metadata.get("id") or metadata.get("name") or default_id))
        document_content = post.content.strip() or content.strip()
        description = str(metadata.get("description") or "")
    elif lowered.endswith((".yaml", ".yml")):
        data = yaml.safe_load(content) or {}
        metadata = dict(data) if isinstance(data, dict) else {}
        document_id = _slugify_name(str(metadata.get("id") or metadata.get("name") or default_id))
        document_content = yaml.safe_dump(data, sort_keys=False) if data else content.strip()
        description = str(metadata.get("description") or "")
    elif lowered.endswith(".json"):
        data = json.loads(content)
        metadata = dict(data) if isinstance(data, dict) else {}
        document_id = _slugify_name(str(metadata.get("id") or metadata.get("name") or default_id))
        document_content = json.dumps(data, indent=2) if data else content.strip()
        description = str(metadata.get("description") or "")
    else:
        metadata = {}
        document_id = default_id
        document_content = content.strip()
        description = ""

    metadata.update(source_metadata)
    metadata.pop("content", None)
    return {
        "id": document_id,
        "type": inferred_type,
        "name": str(metadata.get("name") or document_id),
        "description": description,
        "content": document_content,
        "metadata": metadata,
    }


def _get_repo_metadata(repo_full_name: str) -> dict:
    """Fetch repository metadata needed for subsequent tree and raw content requests."""
    payload = _github_get_json(f"{GITHUB_API_BASE}/repos/{repo_full_name}")
    default_branch = payload.get("default_branch") if isinstance(payload, dict) else None
    return {"default_branch": default_branch or "main"}


def _candidate_score(path: str, candidate_kind: str, query: str) -> int:
    """Score candidate paths so likely knowledge files appear first."""
    lowered = path.lower()
    score = 0
    if f"/knowledge/{candidate_kind}s/" in lowered:
        score += 60
    if f"/{candidate_kind}s/" in lowered:
        score += 25
    if lowered.endswith("skill.md") and candidate_kind == "skill":
        score += 20
    if lowered.endswith(".instructions.md") and candidate_kind == "rule":
        score += 14
    if "/docs/" in lowered or "/prompts/" in lowered:
        score += 6
    if query and query in lowered:
        score += 10
    return score


def _github_get_json(url: str) -> dict:
    """Fetch JSON from the GitHub API."""
    raw = _github_get_text(url, accept="application/vnd.github+json")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub returned an invalid JSON response") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned an unexpected JSON payload")
    return payload


def _github_get_text(url: str, accept: str = "text/plain") -> str:
    """Fetch text content from GitHub with a stable user agent and error mapping."""
    headers = {
        "Accept": accept,
        "User-Agent": "shared-synapse-importer",
    }
    token = os.getenv(_GITHUB_TOKEN_ENV, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        url,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 403 and "rate limit exceeded" in detail.lower():
            raise RuntimeError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN in the backend environment to use authenticated requests."
            ) from exc
        raise RuntimeError(f"GitHub request failed with status {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub request failed: {exc.reason}") from exc


def _raw_content_url(repo_full_name: str, default_branch: str, path: str) -> str:
    """Build a raw GitHub content URL for a repository file."""
    return f"https://raw.githubusercontent.com/{repo_full_name}/{default_branch}/{path}"


def _slugify_name(value: str) -> str:
    """Normalize remote names into the repo's lower-kebab identifier style."""
    normalized = value.strip().replace("_", "-").replace(" ", "-").lower()
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized