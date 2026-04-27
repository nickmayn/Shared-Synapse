---
id: auth-system
title: Authentication System
tags: [auth, security, backend]
owner: platform-team
---

# Authentication System

The authentication system handles all user identity verification and session management.

## Architecture

The auth system uses JWT tokens with short-lived access tokens (15 minutes) and long-lived refresh tokens (7 days).

### Components

- **Token Service**: Issues and validates JWT tokens
- **User Store**: PostgreSQL table storing hashed credentials
- **Session Manager**: Redis-backed session store

## Common Tasks

### Adding a New OAuth Provider

1. Register the provider credentials in `.env`
2. Implement the provider adapter in `src/auth/providers/`
3. Update the OAuth callback handler
4. Add the provider to the frontend login UI

### Debugging Auth Issues

- Check token expiry with `jwt decode <token>`
- Verify Redis session with `redis-cli GET session:<user_id>`
- Review audit logs in `audit_log` table
