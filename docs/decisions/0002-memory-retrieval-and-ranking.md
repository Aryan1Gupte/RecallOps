# ADR 0002: Memory retrieval and deterministic ranking

- Status: Provisional
- Date: 2026-07-04

## Context

RecallOps needs to retrieve prior incident memories without allowing weak semantic matches or language-model judgement to create misleading confidence. Retrieval and ranking must be inspectable, deterministic, and testable. This record proposes the design; it does not add application configuration, persistence, or retrieval code.

The planned configuration names are:

- `MEMORY_SIMILARITY_THRESHOLD`
- `MEMORY_CANDIDATE_LIMIT`
- `MEMORY_RESULT_LIMIT`

These names are documented for the future implementation only and are not part of the current application configuration.

## Decision

Memory retrieval will use two stages: a strict semantic candidate gate followed by deterministic reranking. Metadata may help order candidates only after they pass the semantic gate; metadata must not rescue a semantically irrelevant memory.

### Stage 1: semantic candidate gate

Normal incident retrieval will search only memories whose status is `active`. Vector search will initially retrieve up to 20 candidates, controlled in the future by `MEMORY_CANDIDATE_LIMIT`.

Each candidate must meet a configurable semantic-similarity threshold before reranking. The initial proposed value for `MEMORY_SIMILARITY_THRESHOLD` is `0.60`. This value is provisional and will be tuned using labelled positive, negative, and borderline incident pairs. `MEMORY_RESULT_LIMIT` will cap the final results returned after reranking.

If no candidate passes the semantic threshold, RecallOps must explicitly return a **no relevant memories found** state and investigate the incident from scratch.

### Stage 2: deterministic reranking

Candidates that pass the semantic gate will receive this provisional score:

```text
final_score = 0.70 × semantic_similarity + 0.20 × reliability + 0.10 × same_service
```

`same_service` is `1` when the memory's service matches the current incident's service and `0` otherwise.

Reliability will be calculated from observed feedback using Laplace smoothing:

```text
reliability = (success_count + 1) / (success_count + failure_count + 2)
```

Consequently, a new memory with no observations starts with reliability `0.50`. The database will store `success_count` and `failure_count` as the underlying evidence. Reliability is calculated from those counts rather than invented by an LLM.

Environment will be displayed as context but will not be part of the initial score. It may later be used as a tie-breaker. Recency is not part of the MVP score: an old memory should not be penalised solely because it is old. Supersession is the primary mechanism for marking explicitly outdated memories. Any future recency feature should use successful confirmation rather than mere retrieval as evidence of continued usefulness.

## Explainability

The Memory Inspector will show a score breakdown containing:

- semantic similarity;
- semantic gate result;
- reliability;
- success count;
- failure count;
- same-service bonus;
- final score;
- memory status;
- supersession information.

The breakdown makes both inclusion and ranking decisions auditable without asking a language model to explain or invent a score after the fact.

## Minimal supersession model

The planned fields are:

- `status`;
- `superseded_by`;
- `superseded_at`;
- `supersession_reason`.

The planned statuses are:

- `active`;
- `superseded`;
- `rejected`.

Normal incident retrieval will use only active memories. Superseded and rejected memories will remain visible in the Memory Inspector to preserve audit history.

## Fair comparison demo

Memory-disabled and memory-enabled demo runs must:

- start from the same seeded dataset;
- use the same incident, model settings, and diagnostic tools;
- prevent either comparison run from mutating the shared memory dataset;
- compare tool calls, failed hypotheses, and steps to root cause.

These controls isolate the effect of memory retrieval and avoid giving either run a data or tooling advantage.

## Consequences

The semantic gate can return no results even when metadata looks favourable, which is intentional: investigating from scratch is safer than presenting an irrelevant memory as useful. Ranking remains reproducible from stored evidence and incident metadata. The threshold, limits, weighting, and possible environment tie-breaker remain provisional until labelled evaluations support tuning them.
