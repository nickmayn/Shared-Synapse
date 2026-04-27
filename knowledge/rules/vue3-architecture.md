---
id: rule-vue3-architecture
name: Vue 3 Architecture Rules
description: Composition API, feature organization, and service access patterns for Vue frontends
priority: 45
applies_to: [frontend]
tags: [frontend, vue, architecture]
---

# Rule: Vue 3 Architecture Rules

These rules apply when building Vue 3 features and shared UI modules.

## Rules

1. **Organize by feature** — Keep feature code together and isolate shared modules clearly.
2. **Use Composition API patterns** — Structure components around props, emits, state, computed values, methods, and lifecycle hooks.
3. **Name composables predictably** — Reusable stateful helpers should use the `use...` prefix.
4. **Keep API access in services** — Components should call shared service modules instead of raw fetch logic.
5. **Use Pinia composition stores when state grows** — Keep store logic feature-scoped and ergonomic to consume.
6. **Use TypeScript for complex frontend logic** — Add type annotations where the shape or flow would otherwise be ambiguous.