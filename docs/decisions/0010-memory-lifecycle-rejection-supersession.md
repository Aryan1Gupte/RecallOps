# ADR 0010: Memory lifecycle rejection and supersession

- Status: Accepted for the memory lifecycle milestone
- Date: 2026-08-04

## Context

RecallOps can now persist memories, recall active memories semantically, rank them deterministically, and collect success/failure feedback. The memory schema already has lifecycle fields: `status`, `superseded_by`, `superseded_at`, and `supersession_reason`. Until this milestone, users could not change those fields through supported workflows.

## Decision

Memories are rejected or superseded instead of deleted. Deleting a row would erase operational context and make it harder to understand why a memory stopped appearing in recall. Preserving inactive rows keeps history inspectable through normal memory APIs while keeping current recall focused on active knowledge.

Recall searches active memories only. `rejected` means the memory is intentionally excluded because it is wrong, too vague, or otherwise unsuitable. `superseded` means a newer active memory replaced it. Returning either status in recall would mix stale or disqualified knowledge with current candidate memories.

Lifecycle actions are deterministic database mutations. Rejecting a memory sets `status = rejected`, records a safe reason, and updates `updated_at`. Superseding a memory sets `status = superseded`, records the active replacement memory, timestamps `superseded_at`, stores the reason, and updates `updated_at`. These actions do not call Bedrock, Titan, Nova, vector search, or any LLM.

Supersession requires an active replacement memory. This prevents a memory from pointing at a rejected or already superseded replacement and keeps recall semantics clear: the old memory is inactive, and the replacement remains eligible for future recall.

If a memory is already superseded, the API returns the current superseded state safely rather than rewriting the original audit fields. Rejected memories cannot be superseded through this workflow, and superseded memories cannot be rejected through this workflow.

Automatic stale-memory detection is deferred. RecallOps should first validate manual lifecycle controls before adding heuristics or model-assisted cleanup that could hide memories without explicit user action.

Audit/event tables are deferred. The current row-level lifecycle fields preserve the essential current state and reason. A future milestone can add event history, actor identity, deduplication, and moderation semantics when authentication and product requirements exist.

## Consequences

Recall can stay simple and safe by filtering to active memories. Operators can retire bad or outdated memories without losing history. The tradeoff is that RecallOps currently records only the latest lifecycle state on the memory row; it does not yet keep a full event trail for every lifecycle action.
