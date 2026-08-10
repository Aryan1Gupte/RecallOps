# RecallOps demo script

This script is for a short local demo before the first AWS deployment. It assumes the app is running locally with the configured CockroachDB and Bedrock access. Do not paste `.env`, database URLs, AWS credentials, provider payloads, or raw vectors into the demo.

## Three-minute outline

1. Open RecallOps and select `Demo — Checkout cache latency recurrence`.
   Say: "RecallOps starts with an incident record, then helps us analyze it and learn from it."

2. Click Analyze incident.
   Say: "This is incident-only analysis. It does not use saved memories."

3. Click Generate embedding preview.
   Say: "This creates a semantic fingerprint, but the raw vector stays private." Leave Advanced details closed unless asked.

4. Show the saved-memory panel.
   The seeded data already includes durable memories linked to demo incidents. Say: "RecallOps stores operational memory separately from incidents, with private vectors in CockroachDB."

5. Click Recall similar memories.
   Show the active checkout resolution and replacement procedure. Point at rank, final score, similarity, reliability, same-service indicator, and Why recalled. Say: "Similarity finds related memories; deterministic ranking orders them."

6. Click Run memory-assisted recommendation.
   Show whether memories were used, the likely root cause, recommended next steps, memory influence notes, and the memories that influenced the recommendation. Say: "This is the bounded agent flow: RecallOps recalls active memories from CockroachDB, then asks Bedrock to reason with that context."

7. Click Mark successful on a useful recalled memory.
   Show the success count and reliability update. Say: "Reliability improves as operators mark memories successful."

8. Scroll to Memory Inspector.
   Show total, active, rejected, and superseded counts. Filter by active, rejected, and superseded.

9. Show the seeded lifecycle examples.
   Filter Memory Inspector by rejected to show the vague checkout memory. Filter by superseded to show the older checkout procedure replaced by the better active procedure. Say: "Supersede means a better memory replaces an older one. The older row is preserved but excluded from future recall."

## Seed the demo data

Run a dry-run first:

```bash
backend/.venv/bin/python -m dotenv -f .env run -- \
  backend/.venv/bin/python backend/scripts/seed_demo_data.py --dry-run
```

Apply only when the local CockroachDB and Bedrock/Titan configuration is available:

```bash
backend/.venv/bin/python -m dotenv -f .env run -- \
  backend/.venv/bin/python backend/scripts/seed_demo_data.py --apply
```

Dry-run does not mutate data and does not call Titan. Apply creates missing demo records, skips existing records, rejects the vague checkout memory, supersedes the older checkout procedure, and sets exact demo feedback counts. The script does not wipe non-demo data and does not print database URLs, AWS credentials, provider payloads, or raw vectors.

## Suggested demo records

The seed script creates these exact incidents:

- `Demo — Checkout cache latency`
- `Demo — Checkout cache latency recurrence`
- `Demo — Nightly batch duplicate transaction IDs`
- `Demo — Payment retry storm`
- `Demo — Failed restart action`
- `Demo — Policy document upload timeout` in the `uat` environment

It also creates these memories:

- Active checkout resolution: `Checkout cache latency is resolved by restarting checkout workers and clearing stale cache state.`
- Superseded checkout procedure: `Restart checkout workers when cache latency appears.`
- Replacement checkout procedure: `Restart checkout workers and clear stale cache before retrying checkout traffic.`
- Rejected vague checkout observation: `Checkout was slow and something needed fixing.`
- Duplicate transaction resolution: `Nightly batch failures from duplicate transaction IDs are fixed by deduplicating the source file before replay.`
- Failed action memory: `Restarting the payment worker alone does not fix retry storms caused by downstream provider timeouts.`
- Payment retry procedure: `Payment retry storms should be controlled by pausing retries and draining queues gradually.`
- Document-service observation: `Document upload timeouts can indicate connection pool exhaustion in the document service.`

## What to show

- Select `Demo — Checkout cache latency recurrence`.
- Recall similar memories.
- Show that active checkout memories appear.
- Run memory-assisted recommendation.
- Show that Bedrock uses active recalled memories, not rejected or superseded ones.
- Open Memory Inspector and show total, active, rejected, and superseded counts.
- Filter by rejected and show `Checkout was slow and something needed fixing.`
- Filter by superseded and show `Restart checkout workers when cache latency appears.`
- Show that the replacement memory remains active.
- Mention that feedback counts are seeded so reliability is visible immediately.

## What to avoid showing

- Do not show `.env`, database URLs, AWS credentials, request IDs, account IDs, raw provider payloads, stack traces, or raw vectors.
- Do not lead with Advanced details. Use it only if judges ask how scoring or embedding metadata is represented.
- Do not present RecallOps as deployed, authenticated, streaming, or autonomous. The agent flow is bounded to memory recall plus recommendation; it does not execute external tools or actions.

## Cleanup notes

Do not wipe existing data. The seed script intentionally has no reset flag. Demo incidents are clearly marked with `Demo —`; demo memories are linked to demo incidents. If cleanup is needed, review targeted manual cleanup carefully outside the demo. Memory deletion is intentionally not implemented in the app.
