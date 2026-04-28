![Shared Synapse logo](logo.png)

# Shared Synapse

A Git-backed, Chroma-indexed, MCP-exposed intelligence layer for developers and AI agents. Shared Synapse ingests structured knowledge into a shared memory graph, activates the right synapses for a task, and surfaces the result through a backend MCP server plus a Vue 3 frontend.

## High-Level Concepts

- **Brain stem baseline**: `core-brainstem` is the always-on synapse that represents team-wide rules, workflow constraints, and shared concepts.
- **Optional neurons**: Backend and frontend work activate additional synapses that connect the relevant rules, skills, tools, decisions, and designs.
- **Knowledge-first system**: Markdown, YAML, and JSON files under `knowledge/` and `synapses/` remain the durable source material for the intelligence layer.
- **Ingestion pipeline**: Files are parsed into typed documents, chunked into retrieval-friendly segments, embedded with a sentence-transformer model, and stored in ChromaDB.
- **Hybrid retrieval**: Queries use semantic vector search plus structured metadata filters, then pass through a re-ranking stage to improve relevance.
- **MCP access layer**: The backend FastMCP server exposes search, retrieval, knowledge-management, skill, rule, and synapse operations for multiple agents.

---

## Quick Start

### 1. Start ChromaDB

```bash
docker compose up -d
```

### 2. Install backend dependencies

```bash
cd backend
pip install -e ".[dev]"
```

### 3. Configure backend environment

```bash
cp backend/.env.example backend/.env
# Edit .env as needed
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
```

### 5. Run ingestion

```python
import asyncio
from src.ingestion import run_ingestion

asyncio.run(run_ingestion())
```

Run this from `backend/`.

### 6. Start the backend MCP server

```bash
cd backend
python -m src.mcp_server.server
```

### 7. Start the Vue 3 frontend

```bash
cd frontend
npm run dev
```

---

## Architecture

```
backend/            # Python MCP backend and Chroma-backed ingestion/retrieval code
frontend/           # Vue 3 control surface for synapses and shared memory
knowledge/          # Concepts, decisions, rules, skills, tools, and designs
synapses/           # YAML activation bundles connecting neurons and the core brain stem
```

**Data flow:**
1. Files are parsed (frontmatter + content extracted)
2. Content is chunked (300–800 tokens, 15% overlap, header-aware)
3. Chunks are embedded (`all-MiniLM-L6-v2`, 384-dim)
4. Documents, chunks, and tool definitions stored in ChromaDB collections
5. MCP server receives queries, embeds them, runs HNSW vector search, re-ranks, returns results

---

## MCP Endpoints

| Tool | Description |
|------|-------------|
| `search_knowledge` | Semantic search with optional filters (`type`, `tags`, `context_pack`) |
| `get_document` | Retrieve full document by ID |
| `get_context_pack` | Retrieve a named synapse/context bundle |
| `get_synapse` | Retrieve a named synapse using the new terminology |
| `list_tools` | List and rank tools relevant to a task |
| `execute_tool` | Execute a registered tool by ID with JSON input |
| `add_knowledge` | Add/update a knowledge document directly (re-indexed immediately, shared across all agents) |
| `update_knowledge` | Update an existing document and re-index it; auto-marks dependent skills for refresh |
| `delete_knowledge` | Remove a document and its chunks; marks dependent skills for refresh |
| `reindex_knowledge` | Trigger full re-ingestion from the file system |
| `get_skill` | Retrieve a skill by ID (name, instructions, triggers, dependencies) |
| `list_skills` | List skills, optionally filtered by context tag |
| `upsert_skill` | Create or update a skill; immediately shared with all connected agents |
| `get_rule` | Retrieve a behavioral rule by ID |
| `list_rules` | List rules by priority; optionally filtered by context |
| `nominate_knowledge` | Nominate a knowledge document for inclusion in shared neurons (concurrent users can propose, vote, approve) |
| `list_nominations` | List knowledge nominations filtered by status (`pending`, `approved`, `rejected`) |
| `vote_nomination` | Cast an up/down vote on a pending nomination; each user may vote once |
| `approve_nomination` | Approve a nomination and immediately ingest it into the shared neuron store |
| `reject_nomination` | Reject a nomination without ingesting it |
| `add_conversation_entry` | Append an entry to a user's per-user chronological conversation history |
| `get_conversation` | Retrieve a user's conversation history (optionally scoped to a session), oldest-first |
| `list_conversations` | List all conversation sessions for a user, newest first |

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

- `backend/src/db/` — Chroma-backed CRUD layer for documents, chunks, tools, skills, and rules
- `backend/src/ingestion/` — File parser, token-aware chunker, sentence-transformer embeddings, pipeline orchestrator
- `backend/src/retrieval/` — Hybrid search (vector + filters), result re-ranker
- `backend/src/mcp_server/` — FastMCP server, input validation, audit logging, and synapse access
- `frontend/src/` — Vue 3 application for the Shared Synapse control surface

### Knowledge taxonomy

- `knowledge/skills/` — Reusable workflows.
- `knowledge/rules/` — Durable engineering standards and constraints.
- `knowledge/tools/` — Tool definitions, APIs, and MCP-adjacent integrations.
- `knowledge/decisions/` — Architectural and design decisions.
- `knowledge/concepts/` — High-level concepts and system overviews.
- `knowledge/designs/` — Theme and visual-direction documents.
- `synapses/` — Curated activation bundles that pull from multiple categories.

### Adding knowledge

Drop `.md`, `.yaml`, or `.json` files into the appropriate directory:

- `knowledge/concepts/` → type `concept`
- `knowledge/decisions/` → type `decision`
- `knowledge/designs/` → type `design`
- `knowledge/skills/` → type `skill`
- `knowledge/rules/` → type `rule`
- `knowledge/tools/` → type `tool`
- `synapses/` → type `context_pack`

Then re-run ingestion to index them.

## Bundled Rules and Skills

The repository now ships a first-class set of bundled rules and skills under `knowledge/rules/` and `knowledge/skills/`.

- Rules capture the current engineering standards for API design, backend architecture, Python, frontend runtime and styling, deployment, security, and workflow.
- Skills capture reusable workflows such as adding an MCP or API endpoint, debugging auth, finding external skills, UI and UX review, reading VS Code search results, and agent customization.
- The `core-brainstem`, `backend`, and `frontend` synapses activate the right knowledge bundles for a given neuron or team surface.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMA_HOST` | `localhost` | Chroma server hostname; leave empty to use local persistent storage |
| `CHROMA_PORT` | `8000` | Chroma server port |
| `CHROMA_PATH` | `../.chroma` | Local persistent Chroma path when no host is configured |
| `EMBEDDINGS_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `KNOWLEDGE_REPO_PATH` | `..` | Root path to scan for knowledge and synapse files |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## License

MIT
