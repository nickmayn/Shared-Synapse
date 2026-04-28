import os
from pathlib import Path
from typing import Optional

import chromadb
from dotenv import load_dotenv

load_dotenv()

_client = None

COLLECTION_METADATA: dict[str, dict] = {
    "documents": {},
    "chunks": {"hnsw:space": "cosine"},
    "tools": {},
    "skills": {},
    "rules": {},
    "audit_log": {},
    "nominations": {},
    "conversations": {},
}


def _default_chroma_path() -> str:
    return str(Path(__file__).resolve().parents[3] / ".chroma")


def _build_client():
    chroma_host = os.getenv("CHROMA_HOST", "").strip()
    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))

    if chroma_host:
        return chromadb.HttpClient(host=chroma_host, port=chroma_port)

    chroma_path = Path(os.getenv("CHROMA_PATH", _default_chroma_path()))
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_path))


async def get_client():
    global _client
    if _client is None:
        _client = _build_client()
        for name, metadata in COLLECTION_METADATA.items():
            _client.get_or_create_collection(name=name, metadata=metadata)
    return _client


async def get_collection(name: str):
    client = await get_client()
    metadata = COLLECTION_METADATA.get(name)
    return client.get_or_create_collection(name=name, metadata=metadata)


async def close_client() -> None:
    global _client
    _client = None


async def get_pool():
    return await get_client()


async def close_pool() -> None:
    await close_client()
