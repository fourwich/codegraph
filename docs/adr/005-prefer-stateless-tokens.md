<!-- test fixture for conflicts detection -->
# ADR 005: Prefer stateless tokens

## Status
Accepted

## Decision
We prefer stateless JWT tokens and avoid server-side session state.

## Reason
Stateless tokens scale better and avoid Redis as a single point of failure.

## Alternatives
Considered stateful sessions but rejected them due to ops cost.
