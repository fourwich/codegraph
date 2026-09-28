<!-- test fixture for conflicts detection -->
# ADR 004: Use stateful sessions

## Status
Accepted

## Decision
We use stateful server-side sessions with a Redis store.

## Reason
We must support one-click logout across all devices, which requires
the server to invalidate sessions immediately.
