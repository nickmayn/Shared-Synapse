---
id: rule-python-standards
name: Python Standards
description: Type annotation, docstring, and implementation rules for Python code
priority: 65
applies_to: [backend, all]
tags: [python, quality, backend]
---

# Rule: Python Standards

These rules apply to Python modules, tests, scripts, and service code.

## Rules

1. **Annotate functions and methods** — Use explicit parameter and return types.
2. **Write docstrings for public code** — Follow PEP 257 for modules, classes, and public functions.
3. **Use precise collection types** — Prefer concrete typing such as `List[T]`, `Dict[K, V]`, and `Optional[T]` when appropriate.
4. **Keep error handling specific** — Catch known exceptions and preserve actionable failure modes.
5. **Use immutable defaults** — Never use mutable values as default arguments.
6. **Prefer small, testable functions** — Break large routines into named units with clear responsibilities.
7. **Keep imports clean** — Avoid unused imports and use forward-reference patterns deliberately.