# Synapses

Synapses are activation bundles that connect groups of knowledge objects for a specific team surface, platform, or project area.

## Mental Model

- `core-brainstem` is the always-on baseline for team-wide rules and concepts.
- Additional synapses such as `backend` and `frontend` layer on top when that neuron is active.
- A synapse can include rules, skills, tools, concepts, decisions, and even other synapses.

## Suggested Fields

- `name` — Stable synapse identifier.
- `description` — Short explanation of what this synapse activates.
- `activation` — `core` or `optional`.
- `extends` — Parent synapses this bundle builds on.
- `includes` — Knowledge IDs that become active when the synapse is selected.