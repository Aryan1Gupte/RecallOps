# ADR 0011: Memory Inspector and lifecycle selection UX

- Status: Accepted for the Memory Inspector milestone
- Date: 2026-08-05

## Context

RecallOps can persist memories, recall active memories semantically, rank them deterministically, accept feedback, and mark memories rejected or superseded. Those backend workflows are useful only if operators can see memory state and manage lifecycle changes without inspecting CockroachDB directly.

## Decision

Add a Memory Inspector to the frontend. The inspector is a visibility and management surface over existing memory APIs. It shows memory counts by lifecycle state, filters by status and memory type, and renders memory cards with reliability, linked incident context, lifecycle reasons, and replacement memory metadata.

Lifecycle state is made visible because rejected and superseded memories are intentionally preserved. Operators need to understand why a memory stopped appearing in recall and which replacement superseded an older memory. Hiding inactive rows would make recall behavior look mysterious and would weaken auditability.

Supersession replacement selection uses an active-memory dropdown instead of a raw UUID text field. Users should not need to copy IDs from CockroachDB or another API response during a demo or operational workflow. The dropdown excludes the current memory and labels candidates with memory type, summary, active status, and a short ID hint.

Inactive memories remain inspectable but excluded from recall. `rejected` and `superseded` rows are part of the operational record, but they are not eligible recall candidates and do not accept feedback in this milestone.

The backend memory list/get response can include safe metadata for the inspector: linked incident title/service/environment and replacement memory summary/type/status. These fields are populated through repository-owned joins and do not expose raw vectors, provider payloads, raw SQL internals, AWS metadata, or database connection details.

Advanced memory search, pagination, and audit-event tables are deferred. The current product need is demo usability and lifecycle clarity over the existing dataset size. Future milestones can add full-text search, pagination, event history, actor identity, and audit exports when product requirements justify the extra contracts and storage.

## Consequences

The inspector makes memory state understandable without changing the semantic recall or deterministic ranking algorithm. The tradeoff is that memory management is still simple: filters are basic, lifecycle history is represented by current row fields, and there is no dedicated audit/event stream yet.
