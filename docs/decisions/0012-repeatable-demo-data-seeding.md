# ADR 0012: Repeatable demo data seeding

- Status: Accepted for the demo-readiness milestone
- Date: 2026-08-06

## Context

RecallOps now has enough memory behavior to demo: persisted vector-backed memories, semantic recall, deterministic ranking, feedback counters, rejection, supersession, and Memory Inspector visibility. Manual setup is slow and easy to make inconsistent during a judge demo.

## Decision

Add a script at `backend/scripts/seed_demo_data.py` that creates a repeatable set of demo incidents and memories. The records use stable incident titles and memory summaries so the script can skip existing data and safely rerun.

Demo incident titles are prefixed with `Demo —`. This keeps judge data obvious in the dashboard and makes manual cleanup safer without adding deletion workflows.

Memory creation uses the existing application service and real Titan embeddings when `--apply` is used. This keeps the demo faithful to production behavior: memories are stored with real `VECTOR(1024)` embeddings, and recall demonstrates the actual CockroachDB vector path. Tests and dry-runs do not call Titan.

The script is dry-run by default and requires explicit `--apply` before it mutates data. Dry-run may inspect existing database state, but it does not create records, update lifecycle fields, set feedback counts, or call Titan.

The script avoids deleting data. No reset flag is included in this milestone because accidental deletion is riskier than manually cleaning clearly prefixed demo records. If reset support is added later, it must be restricted to `Demo —` incidents and memories linked to those incidents.

Exact demo feedback counts are set through a small script-local database update scoped to exact memory IDs and summaries. The public feedback workflow intentionally increments counters, which is right for users but not enough for idempotent seeding.

## Consequences

Judges can see a consistent story with active, rejected, and superseded memories, reliability differences, and recall behavior immediately after seeding. The tradeoff is that the script still depends on configured CockroachDB and Titan access for `--apply`, and automated tests continue to avoid real Bedrock and CockroachDB calls.
