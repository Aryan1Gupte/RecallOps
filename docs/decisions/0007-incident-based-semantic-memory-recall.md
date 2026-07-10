# ADR 0007: Incident-based semantic memory recall

- Status: Accepted for the semantic recall milestone
- Date: 2026-07-10

## Context

RecallOps now stores long-term memories with private Titan Text Embeddings V2 vectors in CockroachDB `VECTOR(1024)` columns. The next milestone needs a user-triggered way to find memories that are semantically similar to a selected incident, without implementing the final deterministic ranking formula or agent behavior.

## Decision

Memory recall uses the deterministic incident embedding text as the query. This is the same text shape used by the embedding preview flow, so recall compares saved memories against the operational incident fields the user can inspect: title, description, service, environment, and status. The query excludes database IDs, timestamps, and raw AI analysis output.

Recall searches only memories whose status is `active`. Superseded and rejected memories remain stored for auditability, but they are not candidates for normal recall because they represent stale or intentionally excluded knowledge.

The first semantic gate uses `min_similarity = 0.60`, where similarity is calculated as `1 - cosine_distance`. This value follows the provisional retrieval design and provides a conservative starting point: weak semantic matches should produce an explicit empty result rather than misleading the incident workflow.

The API caps `top_k` at `10` and defaults to `5`. The cap keeps synchronous recall responses small, avoids returning a noisy wall of partially related memories, and limits provider and database work while the UX is still being validated.

Final deterministic ranking is deferred. This milestone orders candidates by CockroachDB cosine distance and applies the semantic gate only. Reliability, same-service weighting, explainability breakdowns, and other ranking terms need their own labelled evaluation and tests before they influence ordering.

CockroachDB vector search remains encapsulated in the memory repository. Services ask for similar active memories; they do not construct SQL. This keeps CockroachDB-specific `VECTOR` casts and `<=>` cosine-distance syntax out of HTTP routes and out of SQLite-focused tests.

## Consequences

Recall is useful enough to validate the memory loop from the incident detail view, but it is not the final retrieval product. Empty recall results are expected when no active memory passes the semantic gate. Public responses include memory metadata, cosine distance, and similarity, but never return query vectors or stored memory vectors.
