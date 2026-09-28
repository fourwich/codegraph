# ADR-005: Prefer stateless JWT without server session state

## Status

Accepted

## Context

Horizontal scale is the top SLO. Avoid sticky sessions and reduce gateway lookups.

## Decision

Always use stateless JWT and never store session state on the server. Disable server-side session caches to keep the edge stateless.

## Consequences

- Simple scaling, weaker revocation.

## Alternatives

- Stateful denylist (rejected for cache ops cost).
