# RecallOps Architecture

> **Status: Provisional.** This document describes the intended direction for the project. The application now has CockroachDB-backed incident CRUD, on-demand Amazon Bedrock analysis, on-demand Titan embedding previews, and persistent long-term memory storage; the broader architecture will evolve as the team validates the incident-response workflow.

## Initial system shape

RecallOps is planned as a web application with a React client and a FastAPI service. The application service will own the incident-response agent loop and coordinate model calls, memory extraction, retrieval, and persistence through explicit interfaces.

CockroachDB Cloud is the implemented persistence layer for incidents and saved memories. Synchronous SQLAlchemy sessions sit behind repository and service functions, Alembic owns schema changes, and FastAPI dependencies provide request-scoped sessions. Amazon Bedrock Runtime provides validated, on-demand incident analysis and normalized Titan Text Embeddings V2 behind separate provider-neutral interfaces. Incident analysis and preview embeddings are not persisted. Memory embeddings are persisted privately as `VECTOR(1024)` and are indexed with CockroachDB vector indexing, but raw vectors are not returned by public APIs or displayed in the frontend. Semantic memory retrieval, vector search endpoints, ranking, MCP, authentication, agent tool execution, and deployment remain unimplemented.

The initial persistence choices are recorded in [ADR 0003: Initial synchronous persistence foundation](decisions/0003-initial-persistence.md).

The initial AI integration choices are recorded in [ADR 0004: On-demand Bedrock incident analysis](decisions/0004-on-demand-bedrock-analysis.md).

The embedding foundation choices are recorded in [ADR 0005: On-demand Titan embedding previews](decisions/0005-on-demand-titan-embedding-previews.md).

The persistent memory storage choices are recorded in [ADR 0006: Persistent memory vector storage](decisions/0006-persistent-memory-vector-storage.md).

## Provisional technology decisions

- CockroachDB Cloud stores structured incident data and vector-backed memory records.
- CockroachDB Distributed Vector Indexing stores the memory embedding index for future semantic recall.
- CockroachDB Managed MCP Server will provide read-only memory inspection.
- Amazon Bedrock will provide the chat model and embeddings.
- The exact chat model will be configured by environment variable.
- Titan Text Embeddings V2 is the planned embedding model.
- AWS App Runner is the planned application host.

## Planned boundaries

- Model providers will sit behind application-owned interfaces so provider details do not leak into incident-response logic.
- Memory extraction will turn incident activity and outcomes into candidate memories.
- Memory retrieval will independently find relevant existing memories for a current incident.
- MCP access will be read-only and intended for inspecting memory, not for silently changing it.
- The application will control agent steps, tool permissions, persistence, and observability.

These boundaries are design intentions, not implemented components.

## Memory retrieval and ranking

The provisional two-stage retrieval, deterministic ranking, supersession, explainability, and fair-comparison design is recorded in [ADR 0002: Memory retrieval and deterministic ranking](decisions/0002-memory-retrieval-and-ranking.md). It is an architecture proposal only and is not implemented in the current scaffold.
