"""Hosted MCP connector discovery helpers backed by Glama search pages."""
from __future__ import annotations

import json
import re
import subprocess
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

GLAMA_CONNECTORS_BASE = "https://glama.ai/mcp/connectors"


def search_hosted_connectors(query: str, limit: int = 8) -> list[dict]:
    """Search Glama hosted MCP connectors using the server-rendered search result metadata."""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    connectors: list[dict] = []
    seen_ids: set[str] = set()
    for candidate_query in _query_variants(normalized_query):
        html = _glama_get_html(f"{GLAMA_CONNECTORS_BASE}?query={quote_plus(candidate_query)}")
        payload = _extract_search_results_payload(html)
        results = payload.get("mainEntity", {}).get("itemListElement", []) if isinstance(payload, dict) else []

        for entry in results[:20]:
            item = entry.get("item") or {}
            page_url = item.get("url") or entry.get("url") or ""
            if not page_url.startswith(f"{GLAMA_CONNECTORS_BASE}/"):
                continue

            connector_id = page_url.removeprefix(f"{GLAMA_CONNECTORS_BASE}/")
            if connector_id in seen_ids:
                continue

            namespace, _, slug = connector_id.partition("/")
            connectors.append(
                {
                    "id": connector_id,
                    "name": item.get("name") or slug or connector_id,
                    "description": item.get("description") or "",
                    "page_url": page_url,
                    "namespace": namespace,
                    "slug": slug or connector_id,
                    "source": "Glama",
                }
            )
            seen_ids.add(connector_id)

    ranked = sorted(
        connectors,
        key=lambda connector: (-_connector_score(connector, normalized_query), connector["name"].lower()),
    )
    return ranked[: max(1, min(limit, 20))]


def _query_variants(query: str) -> list[str]:
    """Return fallback query variants that strip MCP-specific filler words when needed."""
    variants = [query]
    stripped = _strip_noise_terms(query)
    if stripped and stripped.lower() != query.lower():
        variants.append(stripped)
    return variants


def _strip_noise_terms(query: str) -> str:
    """Strip generic MCP filler words from a search phrase."""
    stripped = re.sub(r"\b(hosted|remote|connector|connectors|mcp|server|servers)\b", " ", query, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", stripped).strip()


def _connector_score(connector: dict, query: str) -> int:
    """Prefer connectors whose text actually matches the meaningful search terms."""
    searchable = " ".join(
        [
            connector.get("name", ""),
            connector.get("description", ""),
            connector.get("slug", ""),
            connector.get("namespace", ""),
            connector.get("page_url", ""),
        ]
    ).lower()
    tokens = [token for token in _strip_noise_terms(query).lower().split(" ") if token]
    if not tokens:
        tokens = [token for token in query.lower().split(" ") if token]

    score = 0
    if tokens and all(token in searchable for token in tokens):
        score += 100
    score += sum(20 for token in tokens if token in searchable)
    name = connector.get("name", "").lower()
    slug = connector.get("slug", "").lower()
    score += sum(25 for token in tokens if token in name)
    score += sum(15 for token in tokens if token in slug)
    if name == " ".join(tokens):
        score += 40
    if any(token in slug for token in tokens):
        score += 10
    return score


def _glama_get_html(url: str) -> str:
    """Fetch connector search HTML via curl to avoid intermediary 103 responses from the origin."""
    try:
        result = subprocess.run(
            ["curl", "--fail", "--location", "--silent", "--show-error", url],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("curl is required to search hosted MCP connectors") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"Glama connector search failed: {detail or exc}") from exc
    return result.stdout


def _extract_search_results_payload(html: str) -> dict:
    """Extract the SearchResultsPage JSON-LD block from a Glama connector search page."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_payload = script.string or script.get_text()
        if not raw_payload:
            continue
        payload = json.loads(raw_payload)
        for entry in payload.get("@graph", []):
            if entry.get("@type") == "SearchResultsPage":
                return entry
    raise RuntimeError("Glama connector search returned an unexpected payload")