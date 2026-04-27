---
id: rule-backend-core
name: Backend Core Standards
description: Configuration, logging, migrations, and operational standards for Python services
priority: 90
applies_to: [backend, infrastructure]
tags: [backend, operations, config]
---

# Rule: Backend Core Standards

These rules apply to backend runtime, operational, and security-sensitive code.

## Rules

1. **Configuration belongs in environment-aware settings** — Read secrets and deployment settings from environment variables.
2. **Keep sensitive data out of code** — Never commit credentials, tokens, or fixed secrets.
3. **Use structured logging** — Prefer Python logging with useful context and appropriate log levels.
4. **Do not log sensitive material** — Audit events and debug logs must exclude secrets and personal data.
5. **Treat schema changes as migrations** — Review and test migrations before applying them.
6. **Model auth as dependencies or guards** — Authentication and authorization checks must be explicit in the request path.
7. **Support multiple environments cleanly** — Development and production behavior must differ by configuration, not by code edits.