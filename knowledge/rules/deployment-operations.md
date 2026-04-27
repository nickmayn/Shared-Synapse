---
id: rule-deployment-operations
name: Deployment and Operations Rules
description: Containerization, startup, and reverse-proxy expectations for deployable services
priority: 35
applies_to: [infrastructure, backend]
tags: [deployment, docker, nginx]
---

# Rule: Deployment and Operations Rules

These rules apply when packaging or deploying services and frontends.

## Rules

1. **Prefer multi-stage container builds** — Keep build-time tooling out of runtime images.
2. **Use startup scripts for environment setup** — Centralize runtime initialization such as env injection, cert setup, and migrations.
3. **Serve static assets behind a proper web server when needed** — Use a reverse proxy for static delivery and API forwarding.
4. **Keep deployment steps reproducible** — Startup and migration behavior should be scriptable and deterministic.
5. **Separate build and runtime concerns** — Avoid coupling image build-time settings to runtime environment values.