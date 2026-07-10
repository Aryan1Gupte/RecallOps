# ADR 0005: On-demand Titan embedding previews

- Status: Accepted for the embeddings foundation milestone
- Date: 2026-07-08

## Context

RecallOps needs a semantic representation of incident content before it can design memory storage, indexing, retrieval, and ranking. Building all of those layers simultaneously would make provider correctness, text composition, and schema decisions difficult to validate independently.

## Decision

RecallOps will generate normalized, 1,024-dimensional embeddings on demand with Amazon Titan Text Embeddings V2 through Bedrock Runtime. The embedding provider will remain behind a protocol, and the public preview endpoint will return only model ID, dimension, input token count, and deterministic input text.

The full vector will remain internal to the backend call and will not be returned to the frontend. Embeddings will not be persisted until a dedicated memory schema and vector lifecycle have been designed.

Incident embedding text will contain title, description, service, environment, and status in a fixed order. Database IDs and timestamps are excluded. Incident analysis output is also excluded in this milestone.

## Rationale

Generating embeddings before storage validates the provider call, dimensions, normalization request, token accounting, deterministic text composition, API safety, and frontend workflow without committing to a premature vector schema.

The full vector is large, not meaningful to a user, and easy to expose or persist accidentally if it crosses the public API boundary. Returning metadata demonstrates that generation worked while keeping vector values backend-internal.

IDs and timestamps describe record identity and lifecycle rather than incident meaning. Including them would make semantically identical incidents produce unnecessarily different input text and embeddings. The stable operational fields better represent content intended for future similarity search.

Embedding persistence depends on unanswered questions about memory ownership, extraction, versioning, supersession, re-embedding, and index configuration. Deferring storage prevents an incident row or temporary preview from becoming an accidental memory schema.

Titan Text Embeddings V2 supports normalized 1,024-dimensional vectors and is optimized for retrieval-oriented semantic representation. It prepares RecallOps for later CockroachDB vector storage and search without implementing those features now.

## Consequences

Each preview incurs a synchronous Bedrock request and its result disappears after the response or frontend selection changes. There is no vector search, comparison, caching, batch generation, background processing, or re-embedding workflow in this milestone. Those capabilities require separate architecture decisions and persistent schemas.
