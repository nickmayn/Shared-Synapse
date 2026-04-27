---
id: rule-development-workflow
name: Development Workflow Rules
description: Function ordering, error handling, and review checklist expectations for day-to-day development
priority: 40
applies_to: [backend, frontend, all]
tags: [workflow, review, quality]
---

# Rule: Development Workflow Rules

These rules cover the expected development loop for code changes.

## Rules

1. **Order functions by composition** — Put higher-level composing functions before lower-level helpers when practical.
2. **Group related logic together** — Keep adjacent behavior adjacent in the file.
3. **Handle async failures explicitly** — Use `try`/`catch` or the Python equivalent around operations that can fail.
4. **Return user-meaningful errors** — Avoid opaque error messages when the caller can act on a clearer one.
5. **Avoid hardcoded configuration** — Keep environment-dependent values out of implementation code.
6. **Review against the checklist** — Check architecture, typing, naming, error handling, and hardcoded values before merging.