# RecallOps demo script

This script is for a short local demo before the first AWS deployment. It assumes the app is running locally with the configured CockroachDB and Bedrock access. Do not paste `.env`, database URLs, AWS credentials, provider payloads, or raw vectors into the demo.

## Three-minute outline

1. Open RecallOps and select a checkout incident.
   Say: "RecallOps starts with an incident record, then helps us analyze it and learn from it."

2. Click Analyze with AI.
   Show the summary, hypotheses, and recommended next steps. Keep the focus on operator assistance, not model internals.

3. Click Generate embedding preview.
   Say: "This creates a semantic fingerprint, but the raw vector stays private." Leave Advanced details closed unless asked.

4. Save a memory from the incident.
   Use a clear summary, root cause, and resolution. Say: "Now RecallOps has durable operational memory, separate from the incident."

5. Click Recall similar memories.
   Show rank, final score, similarity, reliability, same-service indicator, and Why recalled. Say: "Similarity finds related memories; deterministic ranking orders them."

6. Click Mark successful on a useful recalled memory.
   Show the success count and reliability update. Say: "Reliability improves as operators mark memories successful."

7. Scroll to Memory Inspector.
   Show total, active, rejected, and superseded counts. Filter by active, rejected, and superseded.

8. Supersede an older disposable memory.
   Use the active-memory dropdown, not a UUID. Say: "Supersede means a better memory replaces an older one. The older row is preserved but excluded from future recall."

## Suggested demo records

Create these manually through the UI. Prefix titles with `Demo -` so they are easy to find later.

### Incident 1

Title: `Demo - checkout-api stale cache latency`

Description: `Checkout requests are timing out after a deploy. Error rates rise when workers reuse stale local cache entries.`

Service: `checkout-api`

Environment: `production`

Useful memory:

- Type: `resolution`
- Summary: `Restarting checkout workers cleared stale local cache and restored checkout latency.`
- Root cause: `Workers kept stale cache entries after deploy.`
- Resolution: `Restart checkout workers and verify cache warmup before declaring recovery.`

### Incident 2

Title: `Demo - nightly batch duplicate transaction identifiers`

Description: `The nightly settlement job produced duplicate transaction identifiers after a retry storm.`

Service: `settlement-batch`

Environment: `production`

Useful memory:

- Type: `procedure`
- Summary: `Pause settlement retries before rerunning duplicate transaction cleanup.`
- Root cause: `Retry workers reused transaction identifier seeds.`
- Resolution: `Pause retries, rotate the batch seed, deduplicate pending rows, then resume the job.`

### Failed action memory

- Type: `failed_action`
- Summary: `Restarting checkout-api alone did not fix stale cache until worker cache was cleared.`
- Root cause: `Restart touched API pods but not the worker cache process.`
- Resolution: `Clear worker cache and restart the worker pool.`

### Superseded memory pair

Older memory:

- Type: `procedure`
- Summary: `Restart checkout-api pods when checkout latency rises.`
- Root cause: `Not provided`
- Resolution: `Restart checkout-api pods.`

Replacement memory:

- Type: `procedure`
- Summary: `Clear checkout worker cache before restarting checkout workers.`
- Root cause: `Workers can retain stale local cache after deploy.`
- Resolution: `Clear worker cache, restart workers, then confirm cache warmup.`

Supersede the older memory with the replacement using the dropdown.

### Rejected vague memory

- Type: `observation`
- Summary: `Things got better after we tried some fixes.`
- Root cause: `Not provided`
- Resolution: `Not provided`

Reject this memory with reason: `Too vague for future operators.`

## What to avoid showing

- Do not show `.env`, database URLs, AWS credentials, request IDs, account IDs, raw provider payloads, stack traces, or raw vectors.
- Do not lead with Advanced details. Use it only if judges ask how scoring or embedding metadata is represented.
- Do not present RecallOps as deployed, authenticated, streaming, or agentic yet. Deployment is the next milestone.

## Cleanup notes

Do not wipe existing data. If you create disposable records, leave them clearly marked with `Demo -` titles or manually reject/supersede disposable memories through the UI. Memory deletion is intentionally not implemented yet.
