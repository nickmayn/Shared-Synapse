---
id: add-api-endpoint
name: Add REST API Endpoint
description: Complete skill for adding a new REST endpoint following team conventions
triggers:
  - add endpoint
  - new route
  - create API
dependencies:
  - auth-system
tags: [api, backend, development]
---

# Skill: Add REST API Endpoint

## When to Use
Use when a new REST endpoint needs to be added to the API gateway.

## Steps

1. **Define route** in `src/api/routes.py` using the router decorator
2. **Create Pydantic models** for request and response in `src/api/models.py`
3. **Implement handler** with proper error handling and logging
4. **Add authentication** — attach the `require_auth` dependency
5. **Validate inputs** — use Pydantic validators or custom checks
6. **Write tests** in `tests/test_api.py` covering success + error paths
7. **Update OpenAPI schema** if using manual spec
8. **Add rate limiting** if the endpoint is public-facing

## Conventions

- Route naming: `kebab-case` paths, `snake_case` parameters
- Return `201` for creation, `200` for reads, `204` for deletes
- Always include request correlation ID in logs
