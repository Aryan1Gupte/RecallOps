# ADR 0013: Bounded memory-assisted incident recommendations

- Status: Accepted for the memory-assisted agent milestone
- Date: 2026-08-07

## Context

RecallOps can analyze incidents, store vector-backed memories, recall active memories with CockroachDB vector search, rank them deterministically, accept feedback, and preserve lifecycle history. Before deployment, the product needs one clear flow where persistent memory directly informs model reasoning instead of appearing as a separate search panel beside incident analysis.

## Decision

Add a bounded endpoint at `POST /api/incidents/{incident_id}/agent-recommendation`. The flow loads the incident, copies its fields into a plain DTO, releases the read transaction, generates a Titan query embedding through the existing embedding boundary, recalls active memories through the existing CockroachDB vector recall service, applies deterministic ranking, releases the recall read transaction, and then asks Bedrock Nova for a structured recommendation using the incident and top recalled memory metadata.

The agent flow is bounded. It does not execute tools, arbitrary SQL, shell commands, deployments, or external actions. It only composes existing application-owned capabilities: incident read, embedding generation, memory recall/ranking, and Bedrock recommendation.

Memory recall happens before LLM reasoning so the model receives relevant operational history at the moment it recommends next steps. This makes the recommendation meaningfully different from incident-only analysis while preserving the deterministic semantic gate and ranking rules already tested by RecallOps.

Recalled memories are passed as structured context: memory type, summary, root cause, resolution, reliability, success/failure counts, final score, and deterministic `why_recalled` text. The prompt tells the model not to blindly copy memories, to mention uncertainty, to prefer higher-reliability memories if context conflicts, and to say when no relevant active memories were found.

Raw vectors remain excluded from both model prompts and public responses. Vectors are private retrieval artifacts, not operator-facing content, and exposing them would increase payload size and accidental leakage risk without helping the recommendation.

Autonomous external action execution is deferred. RecallOps is proving memory-assisted reasoning first; tool execution needs separate authorization, safety controls, auditability, and deployment design.

## Consequences

Judges can see a complete memory-assisted incident recommendation path using seeded demo data. The tradeoff is that recommendations remain synchronous and on demand, are not persisted, and do not mutate operational systems. Paid model calls remain protected by the existing demo-safe rate limiter.
