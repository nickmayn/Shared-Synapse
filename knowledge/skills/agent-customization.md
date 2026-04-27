---
id: agent-customization
name: Agent Customization
description: Create, update, review, and debug agent instructions, prompts, agents, hooks, and skill packages
triggers:
  - customize agent
  - fix instructions
  - create skill
  - debug copilot instructions
dependencies:
  - rule-development-workflow
  - rule-code-quality
tags: [agents, customization, workflow]
---

# Skill: Agent Customization

## When to Use
Use this skill for authoring or debugging customization files such as `copilot-instructions.md`, `*.instructions.md`, `*.prompt.md`, `*.agent.md`, hooks, and `SKILL.md` packages.

## Steps

1. Choose the correct primitive: instructions, prompt, hook, custom agent, or skill.
2. Pick the correct scope: workspace-shared customization or user-level customization.
3. Create or update the file in the correct folder with valid YAML frontmatter.
4. Verify that the description clearly states when the customization should apply.
5. Check for common silent-failure causes such as malformed YAML, bad file placement, or overly broad `applyTo` patterns.

## Notes

- Use instructions for always-on guidance and skills for on-demand workflows.
- Prefer specific `applyTo` globs instead of repository-wide inclusion unless the rule truly applies everywhere.