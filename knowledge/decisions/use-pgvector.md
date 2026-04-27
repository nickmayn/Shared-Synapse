---
id: use-pgvector
title: "Decision: Use pgvector for Vector Storage"
tags: [database, vector, decision]
status: accepted
---

# Decision: Use pgvector for Vector Storage

## Context

We need a vector store for semantic search over knowledge chunks.

## Decision

Use pgvector as a PostgreSQL extension rather than a separate vector database.

## Rationale

- Single infrastructure: no separate vector DB service
- ACID transactions covering both document and vector updates
- pgvector HNSW indexing provides <10ms query latency at our scale
- Simpler ops: one DB to manage

## Consequences

- Embedding dimension limited to 2000 (adequate for all-MiniLM-L6-v2 at 384)
- Must run pgvector-compatible PostgreSQL image
