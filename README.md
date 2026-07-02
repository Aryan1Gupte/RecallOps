# RecallOps

RecallOps is a planned AI incident-response application that helps teams investigate incidents and learn from prior outcomes. This repository currently contains only the initial local development scaffold: a minimal FastAPI backend and a minimal React frontend.

## Planned technology stack

- React, TypeScript, and Vite for the frontend
- Python and FastAPI for the backend
- Amazon Bedrock for chat-model and embedding calls
- CockroachDB Cloud for structured data and vector memory
- CockroachDB Distributed Vector Indexing for semantic recall
- CockroachDB Managed MCP Server for read-only memory inspection
- AWS App Runner for deployment

The cloud, database, model, memory, authentication, and deployment integrations are not implemented yet.

## Prerequisites

- Git
- Python 3.9 or newer
- Node.js 20.19 or newer
- npm

## Backend setup and startup

From the repository root:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -e 'backend[dev]'
uvicorn recallops.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Its health endpoint is `http://127.0.0.1:8000/api/health`.

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

The scaffold reads `APP_NAME`, `APP_ENV`, and `API_PREFIX` from the process environment and provides local-development defaults for each. `.env.example` documents the supported values and contains no credentials. To use a local `.env` file, copy the example and start Uvicorn with `--env-file .env`; otherwise the standard startup command above works with the defaults.
