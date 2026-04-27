---
id: add-api-endpoint
name: Add MCP or API Endpoint
description: Complete skill for adding a new MCP tool or HTTP endpoint using the repo's actual backend structure
triggers:
  - add endpoint
  - new route
  - create API
dependencies:
  - auth-system
  - add-endpoint
  - rule-api-patterns
  - rule-fastapi-architecture
  - rule-python-standards
  - rule-development-workflow
tags: [api, backend, mcp, development]
---

# Skill: Add MCP or API Endpoint

## When to Use
Use when Shared Synapse needs a new MCP tool, a new backend endpoint, or a new knowledge-management operation.

## Steps

1. **Choose the serving surface** — add an MCP tool in `src/mcp_server/server.py` unless an HTTP route is explicitly required.
2. **Define the contract first** — decide input fields, output shape, validation rules, and failure cases.
3. **Keep handler logic thin** — validate at the boundary, then delegate to ingestion, retrieval, or database helpers.
4. **Use existing stores and pipeline modules** — prefer `src/db/` and `src/ingestion/` abstractions over inline SQL or ad hoc file handling.
5. **Audit and validate** — follow the existing patterns for audit logging and validation helpers.
6. **Update knowledge docs if behavior is user-facing** — add or revise supporting rule, skill, or playbook documents.
7. **Write focused tests** — add success and failure coverage in the relevant `tests/` module.
8. **Reindex if the endpoint changes knowledge behavior** — ensure new knowledge types or metadata are discoverable.

## Conventions

- Use descriptive tool or endpoint names that map to a single responsibility.
- Keep JSON arguments strict and validated before any side effects.
- Reuse existing `db_*` and pipeline helpers before introducing new storage code.
- Prefer repository-native documentation over instructions that reference files not present in this repo.
