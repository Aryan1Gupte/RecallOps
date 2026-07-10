# ADR 0006: Persistent memory vector storage

- Status: Accepted for the persistent memory storage milestone
- Date: 2026-07-10

## Context

RecallOps can create incidents, generate on-demand incident analysis, and preview Titan Text Embeddings V2 metadata. The next step is durable long-term memory storage, but not semantic retrieval, ranking, tool execution, or automated extraction.

## Decision

Saved memories are stored in a dedicated `memories` table rather than on incident rows. A memory can optionally link to an incident, but it has its own type, lifecycle status, supersession fields, usage counters, deterministic embedding text, embedding model metadata, and private vector column.

Embeddings are stored on memories rather than incidents because not every incident field is a reusable lesson, and multiple memories can come from one incident. Incident rows remain the operational record; memory rows represent reusable outcomes, observations, procedures, or failed actions.

The memory embedding column uses CockroachDB `VECTOR(1024)` because Titan Text Embeddings V2 is configured through the backend embedding boundary to produce normalized 1,024-dimensional vectors. The backend reuses the shared `EMBEDDING_DIMENSIONS` constant for application validation, while Alembic keeps the historical `VECTOR(1024)` literal in schema DDL.

The raw vector is hidden from public responses and the frontend. Public APIs return memory metadata and deterministic embedding text only. This prevents large, low-value vector payloads from spreading across clients and reduces accidental exposure risk.

Alembic uses raw SQL for the `VECTOR(1024)` column and vector index because those are CockroachDB-specific DDL features that SQLAlchemy and SQLite tests should not need to understand. SQLite tests use repository boundaries and fakes rather than executing CockroachDB vector syntax.

Semantic search endpoints, retrieval, ranking, supersession workflows, and memory usage tracking are deferred. This milestone only proves safe creation, listing, lookup, vector persistence, and index creation.

## Consequences

Memory creation performs a synchronous embedding request before inserting a row. If the embedding provider fails, RecallOps returns a sanitized error and does not persist a partial memory. Future retrieval work can build on the stored vector index without changing the incident schema.
