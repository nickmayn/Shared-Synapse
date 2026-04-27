---
id: find-skills
name: Find Skills
description: Discover installable agent skills when a user asks for a capability, workflow, or specialized domain helper
triggers:
  - find a skill
  - is there a skill for
  - how do I do this with a skill
  - extend capabilities
dependencies:
  - rule-development-workflow
tags: [skills, discovery, workflow]
---

# Skill: Find Skills

## When to Use
Use this skill when the user is looking for an existing installable skill rather than a one-off answer.

## Steps

1. Identify the domain and concrete task the user wants help with.
2. Search the skills ecosystem with a focused query such as `npx skills find react performance`.
3. Return the best-matching skills with the install command and a short explanation of why each one fits.
4. Offer installation with `npx skills add <owner/repo@skill> -g -y` if the user wants to proceed.
5. If no relevant skill exists, continue with direct help or suggest creating a custom skill.

## Notes

- Use specific search terms rather than broad category words.
- Prefer presenting a small number of relevant options over a long unranked list.