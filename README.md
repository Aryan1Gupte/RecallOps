# RecallOps

RecallOps is an evolving AI incident-response application that helps teams investigate incidents and learn from prior outcomes. The current implementation provides CockroachDB-backed incident CRUD, an incident dashboard, on-demand initial analysis, metadata-only Titan embedding previews, and persistent long-term memories backed by CockroachDB VECTOR storage.

## Planned technology stack

- React, TypeScript, and Vite for the frontend
- Python and FastAPI for the backend
- Amazon Bedrock for implemented chat-model analysis and Titan embedding generation
- CockroachDB Cloud for implemented incident and memory persistence
- CockroachDB Distributed Vector Indexing for persisted memory embeddings
- CockroachDB Managed MCP Server for read-only memory inspection
- AWS App Runner for deployment

Incident preview embeddings are generated on demand but are not persisted. Saved memories generate Titan Text Embeddings V2 vectors and store them in CockroachDB as `VECTOR(1024)` with a CockroachDB vector index. Semantic memory recall can retrieve active memories for a selected incident using CockroachDB cosine distance and then order gated candidates with deterministic ranking. Memory feedback controls can increment success and failure counts for active memories so future rankings can use updated reliability. Manual lifecycle controls can reject memories or supersede old memories with active replacements while preserving the original rows. The frontend also includes a Memory Inspector for reviewing saved memories, filtering by lifecycle state/type, and managing active memories without copying raw UUIDs. MCP, authentication, agent tool execution, background jobs, streaming, seed datasets, memory deletion, automatic stale-memory cleanup, and deployment integrations are not implemented yet. AI analysis is also returned on demand and is not stored in the database.

## Prerequisites

- Git
- Python 3.12
- Node.js 24
- npm

The repository-root `.python-version` and `.nvmrc` files document the backend and frontend runtime versions. Version managers such as pyenv and nvm can read these files; before creating the backend virtual environment or installing frontend packages, confirm that your active runtimes report Python 3.12 and Node.js 24.

## Backend setup and startup

From the repository root:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -e 'backend[dev]'
uvicorn recallops.main:app --reload --env-file .env
```

The API is available at `http://127.0.0.1:8000`. Process health is available at `http://127.0.0.1:8000/api/health`, while database health is checked separately at `http://127.0.0.1:8000/api/health/database`.

Run the backend tests with the virtual environment active:

```bash
pytest backend/tests
```

## Frontend setup and startup

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Vite prints the local frontend URL when it starts, normally `http://localhost:5173`.

Build the frontend for production with:

```bash
cd frontend
npm run build
```

For the pre-deployment path, RecallOps expects same-origin serving: when a
built frontend directory exists, the FastAPI app serves it while keeping API
routes under `/api`. By default the backend looks for the repository-local
`frontend/dist`; deployment can set `RECALL_OPS_FRONTEND_DIST` to an explicit
build directory. Local Vite development still uses the Vite proxy, so the
frontend API clients can keep the relative `/api` base path without adding
deployment CORS requirements yet.

## Demo flow

For a short judge demo, use the incident dashboard first, then recall and memory management:

1. Select or create a realistic incident such as checkout latency from stale cache.
2. Run AI analysis to show the on-demand investigation aid.
3. Generate the semantic fingerprint preview to show that vectors stay private.
4. Save one clear memory from the incident.
5. Click Recall similar memories to show ranked recalled memories.
6. Mark a recalled memory successful and point out that reliability improves future ranking.
7. Open Memory Inspector to show active, rejected, and superseded memories.
8. Reject a vague disposable memory or supersede an older memory with a better active replacement.

The main cards are judge-facing and hide implementation details by default. Use **Advanced details** only when you need to show model IDs, embedding dimensions, cosine distance, ranking formula, timestamps, or UUIDs. Raw vectors are never shown. AWS deployment is the next planned milestone; this repo does not yet include deployment, Docker, MCP, authentication, background jobs, streaming, or agent loops.

## Environment configuration

Create a local environment file from the safe template:

```bash
cp .env.example .env
```

Replace the fictional `DATABASE_URL` placeholder in `.env` with the CockroachDB Cloud connection URL. Preserve `sslmode=verify-full`. **Never commit `.env` or paste its contents into logs, issues, or chat.** The file is ignored by Git.

Set `AWS_REGION` to the AWS region where Bedrock is available and `BEDROCK_CHAT_MODEL_ID` to a chat model or inference profile that supports the Converse API. Both values are required only when incident analysis is requested.

Set `BEDROCK_EMBEDDING_MODEL_ID` to the Titan Text Embeddings V2 model used for embedding previews and memory creation. The safe default placeholder is `amazon.titan-embed-text-v2:0`. This setting is required only when an embedding preview or memory creation is requested.

AWS credentials must be configured outside this repository through the normal AWS SDK credential provider chain, such as a local shared AWS profile or an assigned runtime role. Never place or commit AWS keys in `.env`, `.env.example`, source files, tests, or documentation.

`APP_NAME`, `APP_ENV`, `API_PREFIX`, and `RECALL_OPS_FRONTEND_DIST` have development-friendly defaults. `DATABASE_URL` is required only when an endpoint, health check, or migration starts database functionality. Missing embedding configuration does not prevent process health, database health, incident CRUD, or incident analysis from starting.

## Database migrations

Alembic owns database schema changes. From the repository root, apply all migrations while loading the ignored local `.env` file without placing the connection URL in `alembic.ini`:

```bash
backend/.venv/bin/python -m dotenv -f .env run -- \
  backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Inspect the current migration revision with:

```bash
backend/.venv/bin/python -m dotenv -f .env run -- \
  backend/.venv/bin/alembic -c backend/alembic.ini current
```

API tests use isolated in-memory SQLite through FastAPI dependency overrides. They never read, modify, or depend on the real CockroachDB Cloud database. The Alembic migration and database-health endpoint validate real CockroachDB compatibility separately. To explicitly exercise the CockroachDB memory insert path with a fake vector and no Bedrock call, run:

```bash
RECALLOPS_RUN_COCKROACH_INTEGRATION=1 \
  backend/.venv/bin/python -m dotenv -f .env run -- \
  backend/.venv/bin/python -m pytest backend/tests/test_cockroach_memory_integration.py
```

After applying migrations, verify the memory table and vector index in CockroachDB with SQL similar to:

```sql
SHOW TABLES;
SHOW INDEXES FROM memories;
SELECT id, memory_type, embedding_dimension, embedding_model_id
FROM memories
ORDER BY created_at DESC
LIMIT 5;
```

To manually check whether recall's vector search plan can use the CockroachDB vector index, run an `EXPLAIN` against the real cluster without printing the connection URL:

```bash
backend/.venv/bin/python -m dotenv -f .env run -- \
  cockroach sql --url "$DATABASE_URL" --execute "
    EXPLAIN
    WITH query_vector AS (
      SELECT CAST('[' || repeat('0.001,', 1023) || '0.001]' AS VECTOR(1024)) AS v
    )
    SELECT memories.id
    FROM memories, query_vector
    WHERE memories.status = 'active'
    ORDER BY memories.embedding <=> query_vector.v, memories.id
    LIMIT 5;
  "
```

The recall repository orders by the actual vector distance expression first and `memories.id` second for deterministic ties. The manual plan should be reviewed for vector-index usage before production deployment. If the plan does not use the vector index, keep the schema unchanged and investigate CockroachDB planner/index requirements separately.

Do not paste or commit `DATABASE_URL`, `.env`, AWS credentials, or full provider responses while running these checks.

## Incident API examples

Create a fictional incident:

```bash
curl --request POST http://127.0.0.1:8000/api/incidents \
  --header 'Content-Type: application/json' \
  --data '{
    "title": "Checkout latency in fictional store",
    "description": "Example requests are exceeding the fictional latency budget.",
    "service": "checkout-api",
    "environment": "production"
  }'
```

List incidents:

```bash
curl http://127.0.0.1:8000/api/incidents
```

Retrieve an incident by replacing the placeholder with an ID returned by the create request:

```bash
curl http://127.0.0.1:8000/api/incidents/00000000-0000-0000-0000-000000000000
```

Check database reachability without exposing connection details:

```bash
curl http://127.0.0.1:8000/api/health/database
```

Generate an on-demand initial AI analysis by replacing the fictional UUID with an existing incident ID:

```bash
curl --request POST \
  http://127.0.0.1:8000/api/incidents/00000000-0000-0000-0000-000000000000/analysis
```

The response includes a summary, likely category, hypotheses, recommended next steps, cautions, and the configured model ID. Model output is parsed and validated before it is returned. The analysis is not persisted in CockroachDB or browser storage.

Generate metadata for an on-demand Titan embedding by replacing the fictional UUID with an existing incident ID:

```bash
curl --request POST \
  http://127.0.0.1:8000/api/incidents/00000000-0000-0000-0000-000000000000/embedding-preview
```

The response includes the incident ID, model ID, vector dimension, input token count, and deterministic text preview. The full vector is deliberately excluded from the API response and frontend. Preview embeddings are not persisted in CockroachDB or browser storage.

Recall semantically similar active memories for an incident:

```bash
curl --request POST \
  'http://127.0.0.1:8000/api/incidents/00000000-0000-0000-0000-000000000000/memory-recall?top_k=5&min_similarity=0.60'
```

The recall endpoint builds the same deterministic incident embedding text used by the preview flow, generates a Titan query embedding, and searches active memories with CockroachDB `VECTOR` cosine distance using the `<=>` operator. `min_similarity` is the semantic gate: RecallOps converts cosine distance to `semantic_similarity = 1 - cosine_distance`, clamps floating-point noise into the public `0.0` to `1.0` range, and only ranks memories whose similarity is at or above the threshold. The server-owned default and minimum allowed value is `0.60`; lower client values are rejected. Metadata cannot rescue a memory that fails the semantic gate. `top_k` controls the maximum number of returned memories after ranking; the default is `5`, and the maximum is `10`.

Gated candidates are ordered by deterministic ranking:

```text
final_score = 0.70 * semantic_similarity + 0.20 * reliability + 0.10 * same_service_score
reliability = (success_count + 1) / (success_count + failure_count + 2)
```

`same_service_score` is `1.0` when the memory is linked to an incident with the same service as the selected incident and `0.0` otherwise. Recall returns memory metadata, cosine distance, semantic similarity, reliability, same-service metadata, final score, rank, and `why_recalled`. The `why_recalled` explanation is deterministic and generated from the score components; it is not produced by Nova, Titan, or any LLM. Recall never returns the query vector or stored memory vectors. Superseded and rejected memories are preserved in the database but excluded from recall.

## Memory API examples

Create a long-term memory, optionally linked to an incident:

```bash
curl --request POST http://127.0.0.1:8000/api/memories \
  --header 'Content-Type: application/json' \
  --data '{
    "incident_id": "00000000-0000-0000-0000-000000000000",
    "memory_type": "resolution",
    "summary": "Restarting checkout workers cleared stale cache entries.",
    "root_cause": "Workers retained stale cache entries after deploy.",
    "resolution": "Restarted the checkout worker pool."
  }'
```

The backend builds deterministic embedding text from the client-provided memory fields and safe linked incident context, calls the configured Titan embedding model, validates the 1,024-dimensional result, and stores the vector privately in CockroachDB. Public responses include memory metadata and the deterministic embedding text, but intentionally do not include the raw vector.

List memories newest first, with optional filters:

```bash
curl http://127.0.0.1:8000/api/memories
curl 'http://127.0.0.1:8000/api/memories?status=active'
curl 'http://127.0.0.1:8000/api/memories?memory_type=procedure'
curl 'http://127.0.0.1:8000/api/memories?incident_id=00000000-0000-0000-0000-000000000000'
```

Retrieve one memory by ID:

```bash
curl http://127.0.0.1:8000/api/memories/00000000-0000-0000-0000-000000000000
```

Memory list/get responses include derived reliability plus safe inspector metadata when available: linked incident title/service/environment, and replacement memory summary/type/status for superseded memories. These metadata fields help the frontend explain why a memory is active, rejected, or superseded without exposing vectors.

Record feedback for an active memory:

```bash
curl --request POST \
  http://127.0.0.1:8000/api/memories/00000000-0000-0000-0000-000000000000/feedback \
  --header 'Content-Type: application/json' \
  --data '{"outcome": "success"}'

curl --request POST \
  http://127.0.0.1:8000/api/memories/00000000-0000-0000-0000-000000000000/feedback \
  --header 'Content-Type: application/json' \
  --data '{"outcome": "failure"}'
```

Feedback is a pure database mutation and does not call Bedrock, Titan, Nova, or any other model provider. `"success"` increments `success_count`; `"failure"` increments `failure_count`; both update `updated_at`. Feedback is accepted only for active memories. Superseded and rejected memories return a safe conflict response.

Reliability is derived from counts and is not stored as a database column:

```text
reliability = (success_count + 1) / (success_count + failure_count + 2)
```

Examples:

- `0` successes, `0` failures -> `0.50`
- `1` success, `0` failures -> `0.67`
- `2` successes, `0` failures -> `0.75`
- `0` successes, `1` failure -> `0.33`
- `0` successes, `2` failures -> `0.25`

Updated reliability appears in memory list/get responses and in future recall ranking results. The frontend updates visible counts and reliability after feedback, and the user can run recall again to refresh final ranking order. Raw vectors are never returned publicly.

Reject an active memory while preserving the row:

```bash
curl --request POST \
  http://127.0.0.1:8000/api/memories/00000000-0000-0000-0000-000000000000/reject \
  --header 'Content-Type: application/json' \
  --data '{"reason": "This memory was too vague or incorrect."}'
```

If the memory is active, RecallOps sets `status` to `rejected`, stores the reason in `supersession_reason`, updates `updated_at`, and leaves success/failure counters unchanged. If the memory is already rejected, the endpoint returns the current rejected state safely. Superseded memories cannot be rejected through this workflow.

Supersede an active memory with another active memory:

```bash
curl --request POST \
  http://127.0.0.1:8000/api/memories/00000000-0000-0000-0000-000000000000/supersede \
  --header 'Content-Type: application/json' \
  --data '{
    "superseded_by": "11111111-1111-1111-1111-111111111111",
    "reason": "Newer resolution replaced the old procedure."
  }'
```

If both memories exist and the replacement is active, RecallOps sets the original memory to `superseded`, records `superseded_by`, `superseded_at`, `supersession_reason`, and `updated_at`, and does not modify the replacement memory. A memory cannot supersede itself. Rejected memories cannot be superseded through this workflow. If the original memory is already superseded, the endpoint returns the current superseded state safely rather than rewriting its audit fields.

Repeated lifecycle submissions are idempotent replays. Rejecting an already rejected memory returns the current rejected state with `Memory was already rejected.` Superseding an already superseded memory returns the current superseded state with `Memory was already superseded.` Different reasons on replay do not rewrite the original audit reason.

Lifecycle actions are deterministic database mutations and do not call Bedrock, Titan, Nova, vector search, or any other model provider. They do not delete rows. Inactive memories remain available through memory list/get APIs but are excluded from future recall, and feedback remains accepted only for active memories.

## Memory Inspector

The frontend Memory Inspector appears below the incident dashboard. It loads saved memories through `GET /api/memories` and provides:

- total, active, rejected, and superseded counts
- status filter: all, active, rejected, superseded
- memory type filter: all, resolution, failed action, procedure, observation
- refresh control
- cards showing summary, optional root cause/resolution, linked incident metadata, success/failure counts, derived reliability, lifecycle reason, and human-readable replacement memory metadata

For active memories, the inspector exposes Mark successful, Mark failed, Reject memory, and Supersede memory actions. Feedback updates reliability through the same counter endpoint used by recall cards. Reject and supersede actions use the existing lifecycle endpoints and update the visible card after success.

Supersession uses a dropdown of active memories rather than a raw replacement UUID input. The current memory is excluded from its own replacement options. Dropdown labels show the memory type, a shortened summary, active status, and a short ID hint so users can choose a replacement without copying UUIDs from CockroachDB. Recall cards use the same active-memory dropdown.

Rejected and superseded memories remain visible in the inspector, but feedback controls are disabled and the UI explains that inactive memories are preserved and excluded from future recall. Technical fields such as model IDs, dimensions, cosine distance, ranking formula, UUIDs, and timestamps are available under Advanced details instead of being primary card content. Raw memory vectors and query vectors are never displayed. The Memory Inspector is a visibility and management surface only; it is not an agent loop, MCP integration, automatic extraction system, deletion workflow, or deployment feature.

The supported MVP memory types are `resolution`, `failed_action`, `procedure`, and `observation`. The supported statuses are `active`, `superseded`, and `rejected`. Memory rows include `success_count`, `failure_count`, `status`, `superseded_by`, `superseded_at`, and `supersession_reason` so ranking, feedback, and lifecycle workflows have stable storage. This milestone still does not implement memory deletion, automatic stale-memory detection, audit/event tables, or agent retrieval behavior.

Known pre-deployment deferrals are intentional for the single-user demo: supersede concurrency/TOCTOU hardening, frontend API-client consolidation, and full automated CockroachDB vector-search integration coverage. Use the manual `EXPLAIN` and smoke checklist above before deployment work, and keep automated tests isolated from CockroachDB and Bedrock by default.

Never commit `.env`, AWS access keys, session tokens, database URLs, or real provider payloads. AWS credentials should remain outside the repository in the standard AWS SDK credential provider chain.
