---
id: rule-frontend-styling
name: Frontend Styling Rules
description: Styling-system expectations for utility classes, theming, and component-level consistency
priority: 50
applies_to: [frontend]
tags: [frontend, styling, design-system]
---

# Rule: Frontend Styling Rules

Use consistent styling primitives so UI components remain composable and maintainable.

## Rules

1. **Prefer the established styling system** — Use the primary utility framework and shared design tokens first.
2. **Use shared class helpers** — Compose conditional classes through a standard utility rather than ad hoc string logic.
3. **Prefer semantic tokens** — Theme values should come from CSS variables or design-system tokens, not scattered raw values.
4. **Keep component styling local** — Avoid leaking styles across unrelated features.
5. **Use custom CSS sparingly** — Reach for bespoke CSS only when utilities cannot express the requirement cleanly.