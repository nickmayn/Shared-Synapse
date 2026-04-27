---
id: rule-code-quality
name: Code Quality Rules
description: Non-negotiable code quality standards for all contributions
priority: 10
applies_to: [backend, frontend, all]
tags: [quality, standards]
---

# Rule: Code Quality Standards

These rules apply to all code contributions and are enforced automatically.

## Rules

1. **Type hints required** — All Python functions must have complete type annotations
2. **Docstrings required** — All public functions and classes must have docstrings
3. **Test coverage** — New code must have ≥80% test coverage
4. **No bare except** — Always catch specific exception types
5. **Max function length** — Functions must not exceed 50 lines; refactor if longer
6. **No print statements** — Use `logging` for all diagnostic output
7. **Immutable defaults** — Never use mutable default arguments in function signatures
