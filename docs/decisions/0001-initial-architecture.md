# ADR 0001: Start with an application-owned agent loop

- Status: Provisional
- Date: 2026-07-02

## Context

RecallOps needs an incident-response agent that can call a chat model, retrieve relevant memories, inspect operational context, and learn from resolved outcomes. Amazon Bedrock Agents could orchestrate parts of that workflow, but the product behaviour and memory model are still being discovered.

## Decision

The first implementation will use a controlled, application-owned agent loop in the FastAPI service rather than Bedrock Agents.

Amazon Bedrock remains the planned provider for chat-model and embedding calls. The exact chat model will be selected with an environment variable, and Titan Text Embeddings V2 is the planned embedding model. Provider-specific calls will remain behind interfaces.

## Rationale

An application-owned loop gives the project direct control over:

- which tools the model can invoke and when;
- the separation between memory retrieval and memory extraction;
- validation before incident data or learned outcomes are persisted;
- deterministic limits, error handling, logging, and test seams;
- the ability to evolve the workflow during the hackathon without coupling its core logic to a managed orchestration product.

This choice also makes model prompts, tool calls, state transitions, and memory writes easier to observe while the workflow is immature.

## Consequences

The application team will initially own orchestration code and its tests. This creates more local implementation work than delegating orchestration to Bedrock Agents, but it preserves control over the behaviour most central to the product.

The decision is provisional. Bedrock Agents can be reconsidered once the workflow, tool contracts, operational requirements, and benefits of managed orchestration are better understood.

## Related provisional choices

- CockroachDB Distributed Vector Indexing will provide semantic recall.
- CockroachDB Managed MCP Server will provide read-only memory inspection.
- AWS App Runner is the planned application host.
