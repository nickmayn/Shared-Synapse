---
id: rule-api-patterns
name: API Patterns and Contracts
description: Versioning, validation, error handling, and pagination expectations for backend and frontend APIs
priority: 80
applies_to: [backend, api, frontend]
tags: [api, contracts, standards]
---

# Rule: API Patterns and Contracts

Use consistent API behavior so clients, tools, and ingestion jobs can rely on stable contracts.

## Rules

1. **Version public APIs** — Prefer explicit versioned routes such as `/api/v1/...` for HTTP surfaces.
2. **Keep transport thin** — Request handlers validate input and delegate business logic to service-layer code.
3. **Return structured errors** — Use explicit error types and clear response messages.
4. **Validate all inputs** — Parse and validate request payloads, query params, and tool inputs before work begins.
5. **Centralize API clients** — Frontend consumers should use shared client modules with consistent error handling.
6. **Use predictable pagination** — Support `skip` and `limit`-style pagination for list endpoints.
7. **Document breaking changes** — Preserve compatibility where possible and call out intentional contract changes.
8. **Configure CORS deliberately** — Allow only known origins and support environment-specific overrides.