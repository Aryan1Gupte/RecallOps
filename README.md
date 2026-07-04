# RecallOps

RecallOps is a planned AI incident-response application that helps teams investigate incidents and learn from prior outcomes. The current implementation provides a FastAPI backend with CockroachDB Cloud persistence and basic incident creation and retrieval, plus a minimal React frontend.

## Planned technology stack

- React, TypeScript, and Vite for the frontend
- Python and FastAPI for the backend
- Amazon Bedrock for chat-model and embedding calls
- CockroachDB Cloud for implemented incident persistence and planned vector memory
- CockroachDB Distributed Vector Indexing for semantic recall
- CockroachDB Managed MCP Server for read-only memory inspection
- AWS App Runner for deployment

AI models, embeddings, memory, vector search, MCP, authentication, and deployment integrations are not implemented yet.

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

`APP_NAME`, `APP_ENV`, and `API_PREFIX` have development defaults. `DATABASE_URL` is required only when an endpoint, health check, or migration starts database functionality.

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
