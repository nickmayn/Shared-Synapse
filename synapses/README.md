# Synapses

Synapses are activation bundles that connect groups of knowledge objects for a specific team surface, platform, or project area.

## Mental Model

- `core-brainstem` is the always-on baseline for team-wide rules and concepts.
- Additional synapses are optional and user-created by default.
- Example synapses such as `backend` and `frontend` live under `synapse-examples/` and can be copied into `synapses/` when needed.
- A synapse can include rules, skills, tools, concepts, decisions, and even other synapses.

## Suggested Fields

- `name` — Stable synapse identifier.
- `description` — Short explanation of what this synapse activates.
- `activation` — `core` or `optional`.
- `extends` — Parent synapses this bundle builds on.
- `includes` — Knowledge IDs that become active when the synapse is selected.