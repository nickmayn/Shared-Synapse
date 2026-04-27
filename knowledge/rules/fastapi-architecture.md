---
id: rule-fastapi-architecture
name: FastAPI Architecture Rules
description: Service and repository boundaries for FastAPI-style backends and MCP-adjacent Python services
priority: 70
applies_to: [backend, api]
tags: [backend, fastapi, architecture]
---

# Rule: FastAPI Architecture Rules

Use clean layer boundaries for HTTP and tool-serving Python services.

## Rules

1. **Separate transport from business logic** — Routers and tool handlers should validate and orchestrate, not implement core behavior.
2. **Keep business rules in services** — Cross-cutting logic belongs in service-layer functions.
3. **Use repositories or CRUD helpers for persistence** — Database access should stay out of handlers.
4. **Use explicit schemas** — Request and response contracts should be modeled separately from storage models.
5. **Raise domain errors close to the source** — Convert them to transport responses at the boundary.
6. **Keep models descriptive** — Use clear table, field, and schema names that match the domain.
7. **Organize by responsibility** — Keep APIs, services, models, schemas, and core utilities in distinct modules.