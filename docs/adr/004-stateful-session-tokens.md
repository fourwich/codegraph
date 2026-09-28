# ADR-004: Stateful session tokens with server denylist

## Status

Accepted

## Context

Product wants "sign out everywhere" for stolen devices. A stateless JWT cannot be revoked immediately without extra infrastructure.

## Decision

Use stateful JWT sessions with a server-side denylist keyed by jti. The gateway caches denylist entries.

## Consequences

- Immediate global sign-out is possible.
- Gateway needs a shared cache.

## Alternatives

- Pure stateless JWT (rejected for revocation latency).
