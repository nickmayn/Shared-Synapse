---
id: rule-security
name: Security Rules
description: Mandatory security practices enforced for all code and deployments
priority: 100
applies_to: [backend, api, infrastructure]
tags: [security, mandatory]
---

# Rule: Security Practices

High-priority rules enforced for all backend and infrastructure work.

## Rules

1. **Never log secrets** — Tokens, passwords, and API keys must never appear in logs
2. **Input validation** — All external inputs must be validated and sanitized
3. **Parameterized queries** — Never use string interpolation for SQL queries
4. **Auth on all endpoints** — Every API endpoint must have explicit auth or be marked public
5. **Dependency scanning** — Run `pip audit` before merging dependency updates
6. **Secrets in environment** — All secrets must come from environment variables or a secrets manager
7. **Least privilege** — Database roles must only have permissions they need
