# CockroachDB MCP Memory Analyst

This workflow shows how RecallOps can use two CockroachDB capabilities for two
different jobs:

- **Distributed Vector Indexing inside the app** powers runtime semantic recall.
  RecallOps generates a Titan query embedding, searches active memory vectors in
  CockroachDB, applies deterministic ranking, and passes safe memory metadata to
  Bedrock for memory-assisted recommendations.
- **CockroachDB Cloud Managed MCP Server outside the app** gives a read-only
  analyst a way to inspect the same persistent memory layer during demos and
  operations.

The MCP workflow is not part of the React UI and is not an autonomous write
path. It is a read-only operational lens over `incidents` and `memories`.

## Safety Model

- Use read-only database access wherever CockroachDB Cloud and the MCP client
  allow it.
- Do not give MCP a database owner, admin, migration, or write-capable account.
- Do not commit MCP API keys, service-account secrets, bearer tokens, database
  passwords, connection strings, cluster IDs, or copied Cloud Console snippets.
- Do not create, edit, or commit real MCP client config files such as
  `.claude.json`, `.cursor/mcp.json`, or `.vscode/mcp.json`.
- Keep `.env` ignored and do not paste `DATABASE_URL` into prompts, tickets, or
  demo notes.
- During the demo, do not ask MCP to mutate incidents, memories, lifecycle
  status, feedback counters, schema objects, users, grants, or settings.
- Do not select `memories.embedding` or raw query vectors. Prefer metadata
  queries that show summaries, lifecycle state, feedback counts, reliability,
  linked incident service, and supersession metadata.

## Setup Checklist

Use placeholders only in documentation and commits. Perform the real setup
locally in the selected MCP client.

1. In CockroachDB Cloud, create or choose a read-only service account or
   database user for the demo, if required by your Managed MCP Server setup.
2. Open the CockroachDB Cloud Managed MCP Server setup flow in Cloud Console.
3. Copy the generated MCP client configuration into your local client only, such
   as Claude Code, Cursor, or VS Code. Do not paste the real config into this
   repository.
4. Verify the connection with safe read-only checks, for example listing tables
   or counting rows.
5. Confirm the account cannot run writes before the demo. A good demo posture is
   to say: "This MCP analyst can inspect RecallOps memory, but it is not allowed
   to change production data."
6. Close any editor panes that show secrets or real MCP config before recording.

Placeholder-only config shape:

```json
{
  "mcpServers": {
    "cockroachdb-memory-analyst": {
      "command": "<cockroachdb-cloud-managed-mcp-command>",
      "args": ["<placeholder-arg-from-cloud-console>"],
      "env": {
        "COCKROACHDB_CLOUD_API_KEY": "<read-only-api-key-placeholder>"
      }
    }
  }
}
```

Never replace the placeholders above in a committed file.

## Analyst Prompts

Use prompts that explicitly keep the workflow read-only and vector-free.

**Prompt A: memory health by status**

```text
Using the RecallOps CockroachDB database through MCP, summarize memory health by status. Count active, rejected, and superseded memories. Do not show raw vectors. Do not mutate data.
```

**Prompt B: low-reliability memories**

```text
Find RecallOps memories with low reliability. Show summary, service, success_count, failure_count, and why they may need review. Do not show raw vectors. Do not mutate data.
```

**Prompt C: checkout supersession chain**

```text
Show the supersession chain for checkout-related demo memories. Identify the old memory, the replacement memory, and the supersession reason. Do not mutate data.
```

**Prompt D: seeded demo recall inspection**

```text
Inspect the seeded demo dataset. Which active memories would be useful for Demo — Checkout cache latency recurrence, and which rejected/superseded memories should be excluded? Do not show raw vectors. Do not mutate data.
```

**Prompt D2: memory-assisted recommendation context**

```text
Inspect the seeded demo dataset for Demo — Checkout cache latency recurrence. Based on active checkout-related memories and lifecycle status, which memory summaries are likely to be useful context for the memory-assisted recommendation? State that exact per-request recommendation context is shown by the RecallOps API/UI and is not persisted as an audit table. Do not show raw vectors. Do not mutate data.
```

**Prompt E: explain persistent memory**

```text
Explain how RecallOps uses CockroachDB as persistent memory for agentic incident recommendations. Base the answer only on database schema/data visible through MCP. Do not show raw vectors. Do not mutate data.
```

## Suggested Read-Only SQL Shapes

These are examples for the analyst to use through MCP. They intentionally omit
`memories.embedding`.

Count memories by status:

```sql
SELECT
  status,
  count(*) AS memory_count
FROM memories
GROUP BY status
ORDER BY status;
```

List demo incidents:

```sql
SELECT
  title,
  service,
  environment,
  status,
  created_at
FROM incidents
WHERE title LIKE 'Demo —%'
ORDER BY service, title;
```

List memory summaries with derived reliability:

```sql
SELECT
  m.status,
  m.memory_type,
  m.summary,
  i.service,
  i.environment,
  m.success_count,
  m.failure_count,
  CAST(m.success_count + 1 AS FLOAT8)
    / CAST(m.success_count + m.failure_count + 2 AS FLOAT8) AS reliability
FROM memories AS m
LEFT JOIN incidents AS i
  ON m.incident_id = i.id
ORDER BY m.status, reliability ASC, m.created_at DESC
LIMIT 25;
```

Find low-reliability memories:

```sql
SELECT
  m.status,
  m.memory_type,
  m.summary,
  i.service,
  m.success_count,
  m.failure_count,
  CAST(m.success_count + 1 AS FLOAT8)
    / CAST(m.success_count + m.failure_count + 2 AS FLOAT8) AS reliability
FROM memories AS m
LEFT JOIN incidents AS i
  ON m.incident_id = i.id
WHERE CAST(m.success_count + 1 AS FLOAT8)
    / CAST(m.success_count + m.failure_count + 2 AS FLOAT8) < 0.5
ORDER BY reliability ASC, m.updated_at DESC;
```

Show superseded memories with replacement summaries:

```sql
SELECT
  old_memory.memory_type AS old_memory_type,
  old_memory.summary AS old_summary,
  replacement.memory_type AS replacement_memory_type,
  replacement.summary AS replacement_summary,
  replacement.status AS replacement_status,
  old_memory.superseded_at,
  old_memory.supersession_reason
FROM memories AS old_memory
LEFT JOIN memories AS replacement
  ON old_memory.superseded_by = replacement.id
WHERE old_memory.status = 'superseded'
ORDER BY old_memory.superseded_at DESC;
```

List rejected memories with reasons:

```sql
SELECT
  m.memory_type,
  m.summary,
  i.service,
  m.success_count,
  m.failure_count,
  m.supersession_reason AS rejection_reason,
  m.updated_at
FROM memories AS m
LEFT JOIN incidents AS i
  ON m.incident_id = i.id
WHERE m.status = 'rejected'
ORDER BY m.updated_at DESC;
```

Inspect service memory coverage:

```sql
SELECT
  COALESCE(i.service, 'unlinked') AS service,
  SUM(CASE WHEN m.status = 'active' THEN 1 ELSE 0 END) AS active_memories,
  SUM(CASE WHEN m.status = 'rejected' THEN 1 ELSE 0 END) AS rejected_memories,
  SUM(CASE WHEN m.status = 'superseded' THEN 1 ELSE 0 END) AS superseded_memories
FROM memories AS m
LEFT JOIN incidents AS i
  ON m.incident_id = i.id
GROUP BY service
ORDER BY active_memories DESC, service;
```

Inspect demo checkout memories without raw vectors:

```sql
SELECT
  m.status,
  m.memory_type,
  m.summary,
  m.root_cause,
  m.resolution,
  m.success_count,
  m.failure_count,
  m.supersession_reason
FROM memories AS m
LEFT JOIN incidents AS i
  ON m.incident_id = i.id
WHERE i.title LIKE 'Demo — Checkout%'
ORDER BY
  CASE m.status
    WHEN 'active' THEN 1
    WHEN 'superseded' THEN 2
    WHEN 'rejected' THEN 3
    ELSE 4
  END,
  m.created_at;
```

The exact memories used by a single `agent-recommendation` response are not
persisted in this milestone. Use the web app or API response for exact
per-request context. MCP can still inspect the active memory records that are
eligible to influence the seeded checkout recommendation and the inactive
records that should be excluded.

## Demo Segment

Use MCP after the web app has already shown runtime recall and
memory-assisted recommendation:

1. In the web app, select `Demo — Checkout cache latency recurrence`.
2. Click **Recall similar memories** and show active checkout memories.
3. Click **Run memory-assisted recommendation** and show that Bedrock uses the
   recalled active memory metadata.
4. Switch to the MCP client and say: "Now I will ask the CockroachDB Cloud
   Managed MCP Server to inspect the same persistent memory layer from outside
   the app."
5. Run Prompt A to show status counts.
6. Run Prompt C or Prompt D to show rejected and superseded memories are present
   for audit history but excluded from runtime recall.

Keep the segment short: the point is to show that CockroachDB is both the
runtime vector-memory store and the externally inspectable operational memory
layer.

## What MCP Should Not Do In This Milestone

- Do not run `INSERT`, `UPDATE`, `DELETE`, `ALTER`, `DROP`, `CREATE`, `GRANT`,
  `REVOKE`, or `SET CLUSTER SETTING`.
- Do not change memory lifecycle state or feedback counters.
- Do not expose raw vectors.
- Do not become part of the web app request path.
- Do not execute tools or operational actions on behalf of RecallOps.
