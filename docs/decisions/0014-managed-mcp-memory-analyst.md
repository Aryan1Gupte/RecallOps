# ADR 0014: Managed MCP memory analyst

- Status: Accepted for the MCP memory analyst milestone
- Date: 2026-08-10

## Context

RecallOps already uses CockroachDB at runtime for incident persistence,
`VECTOR(1024)` memory storage, distributed vector recall, deterministic ranking,
feedback counters, lifecycle state, and memory-assisted recommendations. The
project also needs a second CockroachDB tool story for judges: CockroachDB Cloud
Managed MCP Server should demonstrate that the persistent memory layer can be
inspected from outside the application.

## Decision

Document a read-only Memory Analyst workflow using CockroachDB Cloud Managed MCP
Server. The workflow is external to the React/FastAPI app: an MCP client connects
to CockroachDB Cloud through the managed MCP setup and inspects RecallOps memory
tables with read-only prompts and metadata-only SQL shapes.

MCP is used as an analyst path rather than a write path. Feedback, rejection,
supersession, and memory creation remain application-owned workflows with tested
validation and safe public responses. The demo analyst should not mutate rows,
schema, cluster settings, feedback counts, or lifecycle state.

Raw vectors remain hidden. The MCP prompts and SQL examples intentionally avoid
`memories.embedding` because vectors are retrieval artifacts, not useful demo
content. The analyst should inspect summaries, lifecycle status, reliability
counts, linked incident metadata, replacement summaries, and rejection or
supersession reasons.

Runtime recall remains application-owned. RecallOps continues to generate Titan
query embeddings, search CockroachDB vectors, apply the semantic gate and
deterministic ranking, and then pass safe recalled memory metadata to Bedrock.
MCP is not in that production request path and does not execute arbitrary tools
or actions.

## Consequences

The demo can show two complementary CockroachDB capabilities: distributed vector
indexing powers the app's live semantic recall, while Managed MCP Server provides
a read-only operational inspection view over the same durable memory layer. The
tradeoff is that the real MCP client setup remains a manual local step, and no
MCP client config or secrets are committed to the repository.
