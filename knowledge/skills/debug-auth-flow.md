---
id: debug-auth-flow
name: Debug Authentication Flow
description: Step-by-step skill for debugging authentication, authorization, and MCP access failures
triggers:
  - auth failure
  - token invalid
  - 401 unauthorized
dependencies:
  - auth-system
  - rule-security
  - rule-backend-core
tags: [auth, debugging, backend]
---

# Skill: Debug Authentication Flow

## When to Use
Use this skill when you encounter JWT authentication errors, authorization failures, or tool-access issues.

## Steps

1. **Confirm the failing boundary**: Identify whether the failure is in token validation, authorization, tool allow-listing, or downstream service access.
2. **Check token lifetime**: Decode the JWT and verify `exp`, `nbf`, and issuer-related claims.
3. **Verify signing inputs**: Confirm the expected secret, key, or certificate is the one used by the running environment.
4. **Inspect session or cache state**: Check backing session storage if the auth flow depends on it.
5. **Review audit and service logs**: Look for validation failures, denied tools, or permission mismatches.
6. **Validate scopes and roles**: Confirm the caller has the permissions required for the endpoint or MCP tool.
7. **Check environment drift**: Ensure clocks, environment variables, and deployed configs match across services.

## Common Causes

- Token expired or not yet valid
- Environment secret or certificate mismatch
- Session state missing or evicted
- Tool blocked by policy or missing permission scope
