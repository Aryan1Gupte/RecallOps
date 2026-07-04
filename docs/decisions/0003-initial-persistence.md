# ADR 0003: Initial synchronous persistence foundation

- Status: Accepted for the initial persistence milestone
- Date: 2026-07-04

## Context

RecallOps now needs durable incident storage and a small CRUD API. This milestone needs a dependable persistence boundary without introducing asynchronous database complexity, AI functionality, or unrelated platform work.

## Decision

The backend will use synchronous SQLAlchemy 2.x sessions with CockroachDB's SQLAlchemy adapter and the synchronous Psycopg 3 driver. Route functions will depend on request-scoped sessions but delegate SQLAlchemy operations to repositories.

Alembic will exclusively own versioned schema changes. Application startup will not create or mutate tables implicitly.

The process-health endpoint and database-health endpoint will remain separate. `/api/health` reports that the API process can respond without touching the database. `/api/health/database` performs a minimal `SELECT 1` and returns only a generic unavailable response on failure.

Database credentials will remain in the `DATABASE_URL` environment variable. The ignored local `.env` file may supply that variable for development, but neither source files nor `alembic.ini` will contain a real connection URL. URL normalization changes only the SQLAlchemy dialect prefix and preserves SSL parameters.

## Rationale

Synchronous SQLAlchemy keeps session lifecycles, transaction behaviour, debugging, and unit tests straightforward for the first persistence milestone. The expected incident CRUD workload does not justify an asynchronous stack yet.

Alembic provides explicit, reviewable, repeatable upgrades and keeps schema history independent from application startup. Separating process and database health distinguishes an unhealthy API process from a temporarily unavailable dependency and prevents the normal liveness check from creating database load or coupling.

Environment variables keep credentials outside version control and allow each runtime environment to supply its own secret without changing application artifacts.

## Consequences

Database work is synchronous and must not be performed directly in async route handlers. Future high-concurrency requirements may justify revisiting this choice, but that would require a separate decision and migration plan.

Tests use isolated SQLite through dependency overrides for fast API and repository validation. Real CockroachDB dialect, migration, TLS, and connectivity behaviour is validated separately against CockroachDB Cloud.
