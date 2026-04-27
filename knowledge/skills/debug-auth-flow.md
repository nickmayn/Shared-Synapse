---
id: debug-auth-flow
name: Debug Authentication Flow
description: Step-by-step skill for debugging JWT authentication failures
triggers:
  - auth failure
  - token invalid
  - 401 unauthorized
dependencies:
  - auth-system
tags: [auth, debugging, backend]
---

# Skill: Debug Authentication Flow

## When to Use
Use this skill when you encounter JWT authentication errors, 401 responses, or session-related failures.

## Steps

1. **Check token expiry**: Decode the JWT and verify `exp` claim is in the future
2. **Verify token signature**: Use `jwt verify <token> <secret>` to confirm signature validity
3. **Inspect Redis session**: Run `redis-cli GET session:<user_id>` to check session exists
4. **Review auth service logs**: Look for `AuthenticationError` or `TokenExpired` entries
5. **Check clock skew**: Ensure server and client clocks are within 5 minutes of each other
6. **Validate scopes**: Confirm the token includes the required permission scopes

## Common Causes

- Token not refreshed after expiry window
- Redis session evicted under memory pressure
- Clock skew between microservices
- Wrong secret used for signing
