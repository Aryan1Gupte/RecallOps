# ADR 0004: On-demand Bedrock incident analysis

- Status: Accepted for the initial AI milestone
- Date: 2026-07-08

## Context

RecallOps needs a first AI capability that can produce an initial analysis for an existing incident. The workflow is still evolving, and this milestone does not include memory, embeddings, vector search, tools, background execution, or long-lived analysis records.

## Decision

Amazon Bedrock Runtime will be accessed through a provider-neutral incident-analysis protocol. The Bedrock implementation will use the synchronous Converse API through boto3 and the normal AWS credential provider chain. Prompt construction, provider calls, model-response parsing, and HTTP routing will remain separate.

Analysis will be generated on demand and returned directly to the caller. It will not be stored in CockroachDB or frontend storage in this milestone.

The model must return strict JSON containing the analytical fields. RecallOps will parse that JSON and validate it with Pydantic before constructing the public response. The application, rather than the model, supplies the trusted incident ID and configured model ID. Invalid or incomplete model output produces a generic upstream error and is never returned raw.

`AWS_REGION` and `BEDROCK_CHAT_MODEL_ID` will be required lazily only when AI analysis is invoked. Process health, database health, and incident CRUD must remain usable without Bedrock configuration.

## Rationale

The protocol keeps HTTP and incident workflows independent from boto3 and preserves a clear test seam for fake providers. It also allows a future model provider to be introduced without moving prompt or SDK logic into route functions.

Not persisting analysis avoids defining lifecycle, freshness, audit, and invalidation semantics before the product has evidence for them. A caller can request a new analysis when needed without creating a misleading durable record.

Model output is untrusted. Strict parsing and schema validation prevent missing fields, additional fields, invalid list shapes, or surrounding commentary from leaking into the API contract.

Lazy configuration isolates optional AI availability from the operational API. A missing model setting should affect only the analysis request, not incident storage or health checks.

## Consequences

Analysis latency is paid during the HTTP request, and results disappear when the page selection changes or the response is discarded. There is no streaming, caching, background execution, or historical analysis in this milestone. Those behaviours require separate design decisions if later evidence justifies them.
