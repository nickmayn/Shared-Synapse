"""Backend entrypoint for the Shared Synapse REST API."""

from __future__ import annotations

import os

import uvicorn

from src.api import app


def main() -> None:
    """Run the FastAPI application with the local development defaults."""
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() in {"1", "true", "yes", "on"}

    uvicorn.run("main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()