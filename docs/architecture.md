# RecallOps Architecture

> **Status: Provisional.** This document describes the intended direction for the project. The application now has CockroachDB-backed incident CRUD, on-demand Amazon Bedrock analysis, on-demand Titan embedding previews, and persistent long-term memory storage; the broader architecture will evolve as the team validates the incident-response workflow.

## Initial system shape

RecallOps is currently an AI-assisted incident memory system with a React client and a FastAPI service. It now includes a bounded memory-assisted incident-agent flow, but autonomous external action execution is not implemented.

CockroachDB Cloud is the implemented persistence layer for incidents and saved memories. Synchronous SQLAlchemy sessions sit behind repository and service functions, Alembic owns schema changes, and FastAPI dependencies provide request-scoped sessions. Amazon Bedrock Runtime provides validated, on-demand incident analysis and normalized Titan Text Embeddings V2 behind separate provider-neutral interfaces. Incident analysis, memory-assisted recommendations, and preview embeddings are not persisted. Memory embeddings are persisted privately as `VECTOR(1024)` and are indexed with CockroachDB vector indexing, but raw vectors are not returned by public APIs or displayed in the frontend. Semantic memory recall searches active memories with CockroachDB cosine distance, applies a server-owned minimum similarity gate of `0.60`, clamps tiny vector-index floating-point noise before ranking, and then orders gated candidates with deterministic scoring from semantic similarity, derived reliability, and same-service metadata. The bounded agent flow is: selected incident -> Titan embedding -> CockroachDB active-memory recall -> deterministic ranking -> top recalled memory metadata -> Bedrock Nova recommendation -> UI. The model sees structured incident and memory context, not raw vectors, raw SQL, or executable tools. Active-memory feedback can atomically increment success or failure counters; reliability remains derived from those counts and affects future rankings. Manual memory lifecycle controls can reject active memories or supersede active memories with active replacements while preserving all rows for audit history. Inactive memories remain visible through memory APIs and the Memory Inspector, but are excluded from recall, feedback, and agent memory context. The Memory Inspector uses the existing memory APIs plus safe linked incident/replacement metadata to make memory state inspectable without exposing raw vectors. Demo-facing UI surfaces rank, final score, similarity, reliability, lifecycle state, and memory-assisted recommendations first, while implementation details such as model IDs, dimensions, cosine distance, ranking formula, timestamps, and UUIDs remain available under Advanced details. For pre-deployment hardening, FastAPI serves only built Vite `dist` artifacts from an explicit `RECALL_OPS_FRONTEND_DIST` directory when configured, or from repository-local `frontend/dist` when present, so production can use same-origin `/api` calls without introducing CORS or serving frontend source files. The Docker image now builds that frontend artifact in a Node 24 stage, copies it into a Python 3.12 FastAPI runtime, includes the public CockroachDB CA certificate for `sslmode=verify-full`, and receives all secrets/configuration through runtime environment variables. Docker startup does not run migrations; Alembic remains an explicit pre-deployment step. Database health verifies reachability plus required migrated tables. Production API docs can be disabled through configuration, and paid Bedrock/Titan HTTP endpoints use a basic process-local fixed-window rate limiter for demo safety. Rate limiting uses `request.client.host` by default instead of trusting user-supplied proxy headers, and stale limiter buckets are evicted in process. Authentication, autonomous external action execution, automatic memory cleanup, memory deletion, audit/event tables, AWS deployment, supersede concurrency hardening, frontend API-client consolidation, and full automated CockroachDB integration coverage remain unimplemented.

CockroachDB Cloud Managed MCP Server is documented as an external read-only analyst path: MCP client -> CockroachDB Cloud Managed MCP Server -> RecallOps `incidents` and `memories` tables. This path is for operational inspection of the same persistent memory layer, not for runtime recall, web-app writes, schema changes, or autonomous actions. The app itself continues to use SQLAlchemy repositories and CockroachDB vector search for production recall.

The initial persistence choices are recorded in [ADR 0003: Initial synchronous persistence foundation](decisions/0003-initial-persistence.md).

The initial AI integration choices are recorded in [ADR 0004: On-demand Bedrock incident analysis](decisions/0004-on-demand-bedrock-analysis.md).

The embedding foundation choices are recorded in [ADR 0005: On-demand Titan embedding previews](decisions/0005-on-demand-titan-embedding-previews.md).

The persistent memory storage choices are recorded in [ADR 0006: Persistent memory vector storage](decisions/0006-persistent-memory-vector-storage.md).

The semantic recall choices are recorded in [ADR 0007: Incident-based semantic memory recall](decisions/0007-incident-based-semantic-memory-recall.md).

The deterministic ranking choices are recorded in [ADR 0008: Deterministic memory recall ranking](decisions/0008-deterministic-memory-recall-ranking.md).

The feedback counter choices are recorded in [ADR 0009: Active memory feedback counters](decisions/0009-active-memory-feedback-counters.md).

The lifecycle control choices are recorded in [ADR 0010: Memory lifecycle rejection and supersession](decisions/0010-memory-lifecycle-rejection-supersession.md).

The inspector and lifecycle UX choices are recorded in [ADR 0011: Memory Inspector and lifecycle selection UX](decisions/0011-memory-inspector-lifecycle-ux.md).

The repeatable demo data choices are recorded in [ADR 0012: Repeatable demo data seeding](decisions/0012-repeatable-demo-data-seeding.md).

The bounded memory-assisted agent choices are recorded in [ADR 0013: Bounded memory-assisted incident recommendations](decisions/0013-bounded-memory-assisted-incident-recommendations.md).

The Managed MCP analyst choices are recorded in [ADR 0014: Managed MCP memory analyst](decisions/0014-managed-mcp-memory-analyst.md).

## Provisional technology decisions

- CockroachDB Cloud stores structured incident data and vector-backed memory records.
- CockroachDB Distributed Vector Indexing stores the memory embedding index for semantic recall.
- CockroachDB Managed MCP Server provides a documented read-only analyst workflow for memory inspection outside the app.
- Amazon Bedrock will provide the chat model and embeddings.
- The exact chat model will be configured by environment variable.
- Titan Text Embeddings V2 is the planned embedding model.
- AWS App Runner is the planned application host.

## Planned boundaries

- Model providers will sit behind application-owned interfaces so provider details do not leak into incident-response logic.
- Memory extraction will turn incident activity and outcomes into candidate memories.
- Memory recall independently finds relevant active memories for a current incident.
- MCP access is read-only and intended for inspecting memory, not for silently changing it.
- A future application layer will control agent steps, tool permissions, persistence, and observability.

These boundaries are design intentions, not implemented components.

## Memory retrieval and ranking

The provisional two-stage retrieval, deterministic ranking, supersession, explainability, and fair-comparison design is recorded in [ADR 0002: Memory retrieval and deterministic ranking](decisions/0002-memory-retrieval-and-ranking.md). Semantic recall now uses CockroachDB vector search for active candidates, applies the semantic gate before metadata scoring, and returns deterministic score explanations. Feedback can update active-memory success/failure counters. Rejection and supersession now change memory lifecycle state through deterministic database mutations; automatic stale-memory detection and deletion remain deferred.
