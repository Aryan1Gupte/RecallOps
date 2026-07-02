# RecallOps Architecture

> **Status: Provisional.** This document describes the intended direction for the project. Only the local FastAPI and React scaffolds exist today, and the architecture will evolve as the team validates the incident-response workflow.

## Initial system shape

RecallOps is planned as a web application with a React client and a FastAPI service. The application service will own the incident-response agent loop and coordinate model calls, memory extraction, retrieval, and persistence through explicit interfaces.

The initial scaffold deliberately excludes all cloud, model, database, MCP, authentication, and deployment integrations.

## Provisional technology decisions

- CockroachDB Cloud will store structured application data and vector memory.
- CockroachDB Distributed Vector Indexing will provide semantic recall.
- CockroachDB Managed MCP Server will provide read-only memory inspection.
- Amazon Bedrock will provide the chat model and embeddings.
- The exact chat model will be configured by environment variable.
- Titan Text Embeddings V2 is the planned embedding model.
- AWS App Runner is the planned application host.

## Planned boundaries

- Model providers will sit behind application-owned interfaces so provider details do not leak into incident-response logic.
- Memory extraction will turn incident activity and outcomes into candidate memories.
- Memory retrieval will independently find relevant existing memories for a current incident.
- MCP access will be read-only and intended for inspecting memory, not for silently changing it.
- The application will control agent steps, tool permissions, persistence, and observability.

These boundaries are design intentions, not implemented components.
