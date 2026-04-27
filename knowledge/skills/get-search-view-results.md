---
id: get-search-view-results
name: Get Search View Results
description: Retrieve the current VS Code Search view results through the built-in command surface
triggers:
  - get search results
  - read search view
  - current search matches
dependencies:
  - rule-development-workflow
tags: [vscode, search, workflow]
---

# Skill: Get Search View Results

## When to Use
Use this skill when there are already results in the VS Code Search view and you need to inspect them programmatically.

## Steps

1. Call the VS Code command `search.action.getSearchResults`.
2. Run it with command-execution support that skips command-existence checks when necessary.
3. Use the returned search results as structured input for the next code or documentation step.