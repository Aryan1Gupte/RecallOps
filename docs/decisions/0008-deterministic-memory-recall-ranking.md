# ADR 0008: Deterministic memory recall ranking

- Status: Accepted for the deterministic ranking milestone
- Date: 2026-07-21

## Context

RecallOps can retrieve active memories with CockroachDB `VECTOR(1024)` cosine-distance search and a semantic gate. The next step is to order those semantically relevant candidates with auditable metadata, without allowing a language model to invent confidence or silently reorder memories.

## Decision

Recall ranking is deterministic instead of LLM-ranked. The backend computes every ranking field from stored memory metadata and the selected incident, then returns the same score breakdown to the frontend. This makes ranking reproducible in tests and keeps model output out of recall explanations.

The semantic gate is applied before ranking. A memory must satisfy `min_similarity` before reliability or same-service metadata can affect ordering. Metadata cannot rescue a semantically irrelevant memory.

Gated candidates use this score:

```text
final_score = 0.70 * semantic_similarity + 0.20 * reliability + 0.10 * same_service_score
```

Semantic similarity has the highest weight because recall should primarily answer whether the saved memory is about a similar operational situation. Reliability and service metadata improve ordering only after the candidate has passed that content-based gate.

Reliability uses Laplace smoothing:

```text
reliability = (success_count + 1) / (success_count + failure_count + 2)
```

This gives new memories a neutral `0.50` reliability instead of treating missing evidence as perfect or useless. The formula remains deterministic and uses stored counts rather than model judgement.

Same-service is a small boost rather than a hard filter. Related incidents can span services, especially in distributed systems, so different-service memories may still be useful when their semantic similarity is high. Same-service matches help order otherwise relevant candidates.

The API returns a short deterministic `why_recalled` explanation assembled from the score components. It does not call Nova, Titan, or any LLM to generate ranking explanations.

Feedback mutation workflows are deferred. This milestone reads `success_count` and `failure_count`, but it does not add feedback buttons, success/failure mutation endpoints, supersession mutation workflows, or agent loops. Those workflows need explicit product semantics and audit behavior before they can update ranking evidence.

## Consequences

Recall results are ordered by final score after semantic gating and are stable under the documented tie-breakers. Weak semantic matches remain excluded even when their metadata is strong. Public responses include score components and explanations, but never include query vectors or stored memory vectors.
