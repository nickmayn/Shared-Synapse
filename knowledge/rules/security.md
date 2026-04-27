---
id: rule-security
name: Security Rules
description: Mandatory security practices enforced for all code and deployments
priority: 100
applies_to: [backend, api, infrastructure]
tags: [security, mandatory]
---

# Rule: Security Practices

High-priority rules enforced for all backend, infrastructure, and externally exposed interfaces.

## Rules

1. **Never log secrets** — Tokens, passwords, and API keys must never appear in logs
2. **Input validation** — All external inputs must be validated and sanitized
3. **Parameterized queries** — Never use string interpolation for SQL queries
4. **Auth on all endpoints** — Every API endpoint must have explicit auth or be marked public
5. **Dependency scanning** — Run `pip audit` before merging dependency updates
6. **Secrets in environment** — All secrets must come from environment variables or a secrets manager
7. **Least privilege** — Database roles must only have permissions they need
8. **No hardcoded credentials** — Development shortcuts must not ship in code or config
9. **Log with context, not payloads** — Keep audit trails useful without exposing sensitive data
10. **Use secure defaults** — Prefer deny-by-default behavior for tools, routes, and permissions
