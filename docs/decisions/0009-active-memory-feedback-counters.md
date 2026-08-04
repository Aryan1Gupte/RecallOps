# ADR 0009: Active memory feedback counters

- Status: Accepted for the memory feedback milestone
- Date: 2026-08-04

## Context

RecallOps ranks recalled memories partly from reliability, which is derived from `success_count` and `failure_count`. Until this milestone, users could see reliability but could not record whether a recalled memory helped or failed.

## Decision

Memory feedback updates counters instead of asking an LLM to judge usefulness. A user action records either `success` or `failure`, and the backend atomically increments the matching counter on the active memory row. This keeps reliability evidence auditable, deterministic, and independent from provider output.

Reliability remains derived rather than stored:

```text
reliability = (success_count + 1) / (success_count + failure_count + 2)
```

Keeping reliability derived prevents drift between counters and score metadata. API responses compute reliability from the current counts, and recall ranking reuses the same formula.

Laplace smoothing gives new memories neutral reliability. With no feedback, a memory starts at `0.50`, so lack of evidence is neither treated as success nor failure. Each user feedback action moves reliability gradually as evidence accumulates.

Feedback applies only to active memories in this milestone. Superseded and rejected memories are not normal recall candidates, so accepting feedback for them would mix current usefulness evidence with lifecycle states that mean stale or intentionally excluded knowledge. Those rows return a safe conflict response.

Feedback event and audit tables are deferred. The current schema stores aggregate counters only, which is enough to validate ranking changes without designing identity, deduplication, event retention, or moderation semantics. A later milestone can add event history if product requirements need it.

Feedback does not automatically rerun recall. The feedback request is a pure database mutation and does not call Bedrock, Titan, Nova, or vector search. The frontend updates visible counts and reliability, then lets the user run recall again when they want refreshed ordering.

## Consequences

Feedback can improve future deterministic rankings without introducing model judgement or raw vector exposure. The tradeoff is that RecallOps stores aggregate evidence only; it cannot yet answer who gave feedback, prevent duplicate feedback, or reconstruct feedback history.
