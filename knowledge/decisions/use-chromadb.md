---
id: use-chromadb
title: "Decision: Use ChromaDB for Shared Synapse Storage"
tags: [database, vector, decision, chroma]
status: accepted
---

# Decision: Use ChromaDB for Shared Synapse Storage

## Context

Shared Synapse needs a storage layer that can hold durable knowledge records, embeddings, and retrieval metadata while remaining simple to operate across multiple repos and future synapse bundles.

## Decision

Use ChromaDB as the primary backing store for documents, chunks, tools, skills, rules, and synapse metadata.

## Rationale

- Chroma gives us a vector-native store without maintaining PostgreSQL-specific vector infrastructure.
- The API aligns with the way Shared Synapse already thinks about collections of documents and chunks.
- It supports a clean separation between repo-root knowledge files and the persisted retrieval index.
- It keeps the migration path open for local persistent storage and service-based deployments.

## Consequences

- Existing pgvector/Postgres-specific deployment assumptions are removed.
- Metadata must be normalized into Chroma-friendly scalar fields for filtering.
- Re-ingestion is the supported path for transferring repo knowledge into the database.