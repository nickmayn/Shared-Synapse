---
id: hybrid-retrieval
title: Hybrid Retrieval
tags: [retrieval, search, vector, ai]
---

# Hybrid Retrieval

Hybrid retrieval combines vector similarity search with structured metadata filtering to improve result quality.

## How It Works

1. **Query Embedding**: The user query is embedded using a sentence transformer model
2. **Vector Search**: Top-N most similar chunks retrieved via cosine similarity
3. **Structured Filtering**: Results filtered by type, tags, ownership
4. **Re-ranking**: Combined score from similarity + metadata relevance

## Why Hybrid

Pure vector search may miss exact matches. Structured filters alone miss semantic meaning. Combining both gives the best results.
