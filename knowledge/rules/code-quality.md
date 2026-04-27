---
id: rule-code-quality
name: Code Quality Rules
description: Baseline code quality and maintainability standards for all contributions
priority: 50
applies_to: [backend, frontend, all]
tags: [quality, standards]
---

# Rule: Code Quality Standards

These rules define the default quality bar for all repository changes.

## Rules

1. **Keep changes minimal** — Only modify code and docs needed for the task.
2. **Prefer readable code** — Choose straightforward implementations over clever abstractions.
3. **Follow existing patterns** — Match naming, structure, and style already used in the repo.
4. **Avoid duplication** — Extract shared logic when repetition becomes operationally expensive.
5. **Use descriptive names** — Name functions, variables, and files by behavior rather than implementation detail.
6. **Favor early returns** — Reduce nested conditionals when a simple guard clause is clearer.
7. **Do not ship dead paths** — Remove unused branches, stale TODOs, and misleading placeholders in touched areas.
8. **Validate behavior** — Run the narrowest useful test or check after changes.
9. **Do not hide failures** — Catch specific exceptions and return actionable errors.
10. **Preserve public APIs unless required** — Avoid incidental breaking changes.
