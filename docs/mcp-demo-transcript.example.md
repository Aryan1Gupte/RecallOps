# MCP Memory Analyst Demo Transcript Example

This is a sanitized example for the optional CockroachDB Cloud Managed MCP
Server segment. It contains no cluster IDs, tokens, database passwords,
connection strings, raw vectors, or real Cloud Console snippets.

## Prompt: Memory Health

```text
Using the RecallOps CockroachDB database through MCP, summarize memory health by status. Count active, rejected, and superseded memories. Do not show raw vectors. Do not mutate data.
```

## Example Response

```text
RecallOps memory health by lifecycle status:

- active: 6 memories
- rejected: 1 memory
- superseded: 1 memory

Active memories remain eligible for semantic recall and memory-assisted
recommendations. Rejected and superseded memories are preserved for review but
excluded from future recall.
```

## Prompt: Checkout Supersession

```text
Show the supersession chain for checkout-related demo memories. Identify the old memory, the replacement memory, and the supersession reason. Do not mutate data.
```

## Example Response

```text
Checkout supersession chain:

- Old memory: procedure - Restart checkout workers when cache latency appears.
- Replacement memory: procedure - Restart checkout workers and clear stale cache before retrying checkout traffic.
- Reason: Newer procedure includes clearing stale cache and warming critical keys, so it is safer than restart alone.

The old memory is still visible for audit history, but its superseded status
means it should not appear in active recall results.
```

## Prompt: Low Reliability Review

```text
Find RecallOps memories with low reliability. Show summary, service, success_count, failure_count, and why they may need review. Do not show raw vectors. Do not mutate data.
```

## Example Response

```text
Low-reliability memories to review:

- observation - Document upload timeouts can indicate connection pool exhaustion in the document service.
  service: document-service
  success_count: 0
  failure_count: 1
  reliability: 0.33
  review note: This memory has more failures than successes and may need a clearer resolution or more validation before operators rely on it.
```

Use this transcript as a shape for the demo, not as committed evidence from a
specific cluster.
