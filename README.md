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

Incident preview embeddings are generated on demand but are not persisted. Saved memories generate Titan Text Embeddings V2 vectors and store them in CockroachDB as `VECTOR(1024)` with a CockroachDB vector index. Semantic memory retrieval, vector search API endpoints, ranking, MCP, authentication, agent tool execution, background jobs, streaming, seed datasets, and deployment integrations are not implemented yet. AI analysis is also returned on demand and is not stored in the database.

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

## Environment configuration

Create a local environment file from the safe template:

```bash
cp .env.example .env
```

Replace the fictional `DATABASE_URL` placeholder in `.env` with the CockroachDB Cloud connection URL. Preserve `sslmode=verify-full`. **Never commit `.env` or paste its contents into logs, issues, or chat.** The file is ignored by Git.

Set `AWS_REGION` to the AWS region where Bedrock is available and `BEDROCK_CHAT_MODEL_ID` to a chat model or inference profile that supports the Converse API. Both values are required only when incident analysis is requested.

Set `BEDROCK_EMBEDDING_MODEL_ID` to the Titan Text Embeddings V2 model used for embedding previews and memory creation. The safe default placeholder is `amazon.titan-embed-text-v2:0`. This setting is required only when an embedding preview or memory creation is requested.

AWS credentials must be configured outside this repository through the normal AWS SDK credential provider chain, such as a local shared AWS profile or an assigned runtime role. Never place or commit AWS keys in `.env`, `.env.example`, source files, tests, or documentation.

`APP_NAME`, `APP_ENV`, and `API_PREFIX` have development defaults. `DATABASE_URL` is required only when an endpoint, health check, or migration starts database functionality. Missing embedding configuration does not prevent process health, database health, incident CRUD, or incident analysis from starting.

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

API tests use isolated in-memory SQLite through FastAPI dependency overrides. They never read, modify, or depend on the real CockroachDB Cloud database. The Alembic migration and database-health endpoint validate real CockroachDB compatibility separately.

After applying migrations, verify the memory table and vector index in CockroachDB with SQL similar to:

```sql
SHOW TABLES;
SHOW INDEXES FROM memories;
SELECT id, memory_type, embedding_dimension, embedding_model_id
FROM memories
ORDER BY created_at DESC
LIMIT 5;
```

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

The response includes the incident ID, model ID, vector dimension, input token count, and deterministic text preview. The full vector is deliberately excluded from the API response and frontend. Preview embeddings are not persisted in CockroachDB or browser storage; vector search and memory retrieval remain unimplemented.

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

The supported MVP memory types are `resolution`, `failed_action`, `procedure`, and `observation`. The supported statuses are `active`, `superseded`, and `rejected`. Semantic search, memory ranking, supersession workflows, usage tracking, and retrieval endpoints are still deferred to later milestones.

Never commit `.env`, AWS access keys, session tokens, database URLs, or real provider payloads. AWS credentials should remain outside the repository in the standard AWS SDK credential provider chain.
