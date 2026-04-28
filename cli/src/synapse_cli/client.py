"""HTTP client for the Synapse REST API."""
import json
from typing import Any, Optional

import httpx

from .config import (
    get_access_token,
    get_refresh_token,
    get_server_url,
    set_profile,
)


class SynapseClient:
    """Thin wrapper around httpx that handles JWT auth + transparent refresh."""

    def __init__(self, profile: str = "default"):
        self._profile = profile
        self._base = get_server_url(profile)
        self._token = get_access_token(profile)

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _refresh(self) -> bool:
        refresh = get_refresh_token(self._profile)
        if not refresh:
            return False
        try:
            resp = httpx.post(
                f"{self._base}/auth/refresh",
                json={"refresh_token": refresh},
                timeout=15,
            )
            if resp.status_code == 200:
                new_token = resp.json()["access_token"]
                self._token = new_token
                set_profile({"access_token": new_token}, self._profile)
                return True
        except Exception:
            pass
        return False

    def request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self._base}{path}"
        resp = httpx.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if resp.status_code == 401 and self._refresh():
            resp = httpx.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get(self, path: str, **kwargs) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self.request("DELETE", path, **kwargs)

    # ---------------------------------------------------------------------------
    # High-level helpers
    # ---------------------------------------------------------------------------

    def search(self, query: str, filters: Optional[dict] = None) -> dict:
        params: dict = {"query": query}
        if filters:
            params["filters"] = json.dumps(filters)
        return self.get("/api/search", params=params)

    def add_knowledge(self, doc_id: str, doc_type: str, content: str, metadata: Optional[dict] = None) -> dict:
        return self.post("/api/knowledge", json={
            "id": doc_id,
            "type": doc_type,
            "content": content,
            "metadata": metadata or {},
        })

    def list_synapses(self) -> list:
        return self.get("/api/synapses").get("synapses", [])

    def activate_synapse(self, name: str) -> dict:
        return self.post(f"/api/synapses/{name}/activate")

    def deactivate_synapse(self, name: str) -> dict:
        return self.post(f"/api/synapses/{name}/deactivate")
