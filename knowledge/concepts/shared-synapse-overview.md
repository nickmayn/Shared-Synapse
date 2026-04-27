---
id: shared-synapse-overview
title: Shared Synapse Overview
tags: [architecture, concept, overview]
---

# Shared Synapse Overview

Shared Synapse is a shared knowledge and tool memory layer for developers and AI agents.

## Core Ideas

1. **Knowledge as source material**: Markdown, YAML, and JSON files define the reusable knowledge that gets indexed.
2. **Typed ingestion**: Files are parsed into concepts, decisions, rules, skills, designs, tools, and context packs.
3. **Retrieval over recall**: Agents fetch relevant documents and chunks at runtime instead of relying on static prompt stuffing.
4. **Shared operational surface**: MCP tools expose knowledge lookup, rule lookup, skill lookup, and knowledge mutation APIs.

## Why It Exists

The goal is to keep durable project knowledge in versioned files while making it searchable and consumable by multiple agents and developer workflows.