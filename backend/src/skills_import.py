"""skills.sh-backed search helpers for discoverable skill results."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

SKILLS_API_BASE = "https://skills.sh"


def search_skills(query: str, limit: int = 50) -> list[dict]:
    """Search the public skills.sh directory for matching skills."""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    payload = _skills_get_json(
        f"{SKILLS_API_BASE}/api/search?q={quote_plus(normalized_query)}&limit={max(1, min(limit, 100))}"
    )
    skills = payload.get("skills", []) if isinstance(payload, dict) else []
    return [
        {
            "id": skill.get("id", ""),
            "skill_id": skill.get("skillId") or skill.get("name") or "",
            "name": skill.get("name") or skill.get("skillId") or "",
            "installs": int(skill.get("installs") or 0),
            "source": skill.get("source") or "",
            "page_url": f"{SKILLS_API_BASE}/{skill.get('id', '')}",
            "github_url": f"https://github.com/{skill.get('source', '')}" if skill.get("source") else "",
        }
        for skill in skills
        if skill.get("id") and skill.get("source") and (skill.get("skillId") or skill.get("name"))
    ]


def _skills_get_json(url: str) -> dict:
    """Fetch JSON from skills.sh with stable error mapping."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "shared-synapse-importer",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"skills.sh request failed with status {exc.code}: {detail or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"skills.sh request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("skills.sh returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("skills.sh returned an unexpected JSON payload")
    return payload