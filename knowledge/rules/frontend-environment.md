---
id: rule-frontend-environment
name: Frontend Environment Rules
description: Runtime configuration and environment-variable patterns for Vite-style frontends
priority: 55
applies_to: [frontend]
tags: [frontend, environment, runtime]
---

# Rule: Frontend Environment Rules

Frontend configuration should stay portable across local development, Docker runtime injection, and production builds.

## Rules

1. **Use `VITE_`-prefixed build variables** — Client-side environment values must follow the framework convention.
2. **Support runtime injection** — Prefer runtime config via `window.__ENV__` when values must change after build time.
3. **Centralize runtime config access** — Read environment values through a shared config utility or composable.
4. **Initialize config before app startup** — Ensure runtime state is loaded before the UI depends on it.
5. **Keep defaults explicit** — Provide safe fallback values for optional config.