import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from ..db import upsert_document, upsert_chunk, upsert_tool, delete_chunks_for_document, delete_document
from ..db.skills_store import upsert_skill, mark_skills_for_refresh
from ..db.rules_store import upsert_rule
from .parser import parse_file
from .chunker import chunk_text
from .embeddings import embed_texts

logger = logging.getLogger(__name__)

KNOWLEDGE_DIRS = ["knowledge", "context-packs", "registry"]
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".yaml", ".yml", ".json"}


def _get_all_files(repo_path: str) -> List[str]:
    files = []
    for dir_name in KNOWLEDGE_DIRS:
        dir_path = Path(repo_path) / dir_name
        if not dir_path.exists():
            continue
        for ext in SUPPORTED_EXTENSIONS:
            for f in dir_path.rglob(f"*{ext}"):
                files.append(str(f))
    return sorted(files)


async def ingest_file(file_path: str) -> bool:
    """Ingest a single file. Returns True on success."""
    try:
        parsed = parse_file(file_path)
        if parsed is None:
            return False

        doc_id = parsed["id"]
        doc_type = parsed["type"]
        content = parsed["content"]
        metadata = parsed["metadata"]

        await upsert_document(doc_id, doc_type, content, metadata)

        if doc_type == "tool":
            try:
                tool_data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                tool_data = {}
            await upsert_tool(
                id=doc_id,
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("input_schema", {}),
                output_schema=tool_data.get("output_schema", {}),
                metadata=tool_data.get("metadata", {}),
            )

        elif doc_type == "skill":
            await upsert_skill(
                id=doc_id,
                name=metadata.get("name", doc_id),
                description=metadata.get("description", ""),
                instructions=content,
                triggers=metadata.get("triggers", []),
                dependencies=metadata.get("dependencies", []),
                metadata={k: v for k, v in metadata.items()
                          if k not in ("name", "description", "triggers", "dependencies")},
            )

        elif doc_type == "rule":
            await upsert_rule(
                id=doc_id,
                name=metadata.get("name", doc_id),
                description=metadata.get("description", ""),
                content=content,
                priority=int(metadata.get("priority", 0)),
                applies_to=metadata.get("applies_to", []),
                metadata={k: v for k, v in metadata.items()
                          if k not in ("name", "description", "priority", "applies_to")},
            )

        chunks = chunk_text(content, doc_id)
        if not chunks:
            return True

        chunk_texts_list = [c["content"] for c in chunks]
        embeddings = embed_texts(chunk_texts_list)

        await delete_chunks_for_document(doc_id)

        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**chunk["metadata"], "document_type": doc_type}
            if "tags" in metadata:
                chunk_meta["tags"] = metadata["tags"]
            if "context_pack" in metadata:
                chunk_meta["context_pack"] = metadata["context_pack"]
            await upsert_chunk(
                id=chunk["id"],
                document_id=doc_id,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk_meta,
            )

        logger.info(f"Ingested {file_path}: {len(chunks)} chunks")
        return True

    except Exception as e:
        logger.error(f"Failed to ingest {file_path}: {e}", exc_info=True)
        return False


async def run_ingestion(repo_path: Optional[str] = None) -> dict:
    """Run full ingestion pipeline. Returns summary stats."""
    if repo_path is None:
        repo_path = os.getenv("KNOWLEDGE_REPO_PATH", ".")

    files = _get_all_files(repo_path)
    logger.info(f"Found {len(files)} files to ingest from {repo_path}")

    success = 0
    failed = 0
    for f in files:
        ok = await ingest_file(f)
        if ok:
            success += 1
        else:
            failed += 1

    return {"total": len(files), "success": success, "failed": failed}


async def delete_knowledge(doc_id: str) -> bool:
    """
    Remove a document and its chunks from the database.
    Marks any skills that depended on this document as needing refresh.
    Returns True on success.
    """
    try:
        await mark_skills_for_refresh([doc_id])
        await delete_chunks_for_document(doc_id)
        await delete_document(doc_id)
        logger.info(f"Deleted knowledge document: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}", exc_info=True)
        return False
