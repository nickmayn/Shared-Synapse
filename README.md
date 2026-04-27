# Shared Synapse

A Git-backed, database-indexed, MCP-exposed intelligence layer for developers and AI agents. Shared Synapse ingests structured knowledge (docs, playbooks, decisions, tool registries) into a PostgreSQL + pgvector store and surfaces it through a Model Context Protocol (MCP) server.

---

## Quick Start

### 1. Start PostgreSQL with pgvector

```bash
docker compose up -d
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env as needed
```

### 4. Run ingestion

```python
import asyncio
from src.ingestion import run_ingestion

asyncio.run(run_ingestion())
```

### 5. Start the MCP server

```bash
python -m src.mcp_server.server
```

---

## Architecture

```
knowledge/          # Markdown docs (systems, concepts, playbooks, decisions)
context-packs/      # YAML bundles of related knowledge
registry/           # JSON tool definitions
src/
  db/               # asyncpg connection pool, documents, chunks, tools tables
  ingestion/        # Parser → Chunker → Embeddings → DB pipeline
  retrieval/        # Hybrid vector + metadata search + re-ranking
  mcp_server/       # FastMCP server exposing 5 tools + security/audit layer
tests/              # pytest test suite
```

**Data flow:**
1. Files are parsed (frontmatter + content extracted)
2. Content is chunked (300–800 tokens, 15% overlap, header-aware)
3. Chunks are embedded (`all-MiniLM-L6-v2`, 384-dim)
4. Documents, chunks, and tool definitions stored in PostgreSQL + pgvector
5. MCP server receives queries, embeds them, runs HNSW vector search, re-ranks, returns results

---

## MCP Endpoints

| Tool | Description |
|------|-------------|
| `search_knowledge` | Semantic search with optional filters (`type`, `tags`, `context_pack`) |
| `get_document` | Retrieve full document by ID |
| `get_context_pack` | Retrieve a named context pack |
| `list_tools` | List and rank tools relevant to a task |
| `execute_tool` | Execute a registered tool by ID with JSON input |

### Example: search_knowledge

```json
{
  "query": "how does authentication work",
  "filters": "{\"tags\": [\"auth\", \"backend\"]}"
}
```

### Example: list_tools

```json
{
  "task": "manage API routes",
  "context": "backend infrastructure"
}
```

---

## Development

### Run tests

```bash
pytest
```

### Project layout

- `src/db/` — Database layer (asyncpg pool, CRUD for documents/chunks/tools, schema)
- `src/ingestion/` — File parser, token-aware chunker, sentence-transformer embeddings, pipeline orchestrator
- `src/retrieval/` — Hybrid search (vector + filters), result re-ranker
- `src/mcp_server/` — FastMCP server, input validation, audit logging

### Adding knowledge

Drop `.md`, `.yaml`, or `.json` files into the appropriate directory:

- `knowledge/systems/` → type `system`
- `knowledge/concepts/` → type `concept`
- `knowledge/playbooks/` → type `playbook`
- `knowledge/decisions/` → type `decision`
- `context-packs/` → type `context_pack`
- `registry/` → type `tool`

Then re-run ingestion to index them.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://synapse:synapse@localhost:5432/synapse` | PostgreSQL connection string |
| `EMBEDDINGS_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `KNOWLEDGE_REPO_PATH` | `.` | Root path to scan for knowledge files |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## License

MIT
