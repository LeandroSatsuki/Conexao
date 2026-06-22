# Architecture

`Preferenza Connector` uses layered architecture to keep concerns separated.

## Layers
- Connectors: communicate with external systems.
- Flows: define what integrates, between which systems, and on which trigger.
- Mappings: transform fields between source and target payloads.
- Executions: record jobs, attempts, responses, and failures.
- Business rules: validate payloads before sending.
- Observability: logs, status, errors, audit, and traceability.

## Current structural base
- `tenants` define the multi-tenant scope.
- `connections` store encrypted credentials and connection metadata.
- `integration_flows` define source, target, and trigger metadata.
- `field_mappings` define explicit, testable field transformations.
- `sync_jobs` record execution state, attempts, and idempotency.
- `integration_logs` record technical audit data with duration and error classification.
- `integration_errors` persist failures for diagnosis and future reprocessing.

## Current MVP behavior
- FastAPI is the API layer.
- PostgreSQL is the operational database.
- Redis is the queue broker and task support backend for Celery.
- Celery runs integration jobs asynchronously in a dedicated worker.
- Sankhya is the first connector.
- Manual flow execution is scheduled through Celery and still uses a simulated runner in this stage, with no real external API call.
- Sankhya connection testing can run in mock mode or real OAuth mode without persisting tokens.
- Sankhya read-only flows use `integration_flows.config_json` to describe `loadRecords` operations and run asynchronously through the same worker path.

## Practical decisions
- UUIDs are stored as strings for portability.
- Credentials are persisted encrypted.
- The API returns masked credentials only as metadata.
- Connection tests write technical logs.
- Duplicate flow execution can return an `ignored` job record when the same payload already succeeded.
- Retryable failures advance through `retrying` and end in `dead_letter` when attempts are exhausted.
- Reprocess preserves history by creating a fresh execution attempt instead of rewriting previous logs.
- `correlation_id` ties a job, its logs, and its errors together.
- Sankhya authentication uses `client_id`, `client_secret`, and `X-Token` against `/authenticate`.
- Read-only Sankhya flow jobs keep the access token in memory only, persist masked payload samples, and record `records_count` for traceability.

## Async execution flow
1. The API creates a `pending` `sync_job`.
2. The API enqueues `execute_flow_job(job_id)` to Celery.
3. The worker loads the job, flow, connections, and mappings.
4. The runner applies the mapper and executes the mocked target call.
5. The worker persists `success`, `failed`, `retrying`, `dead_letter`, or `cancelled` state.
6. Logs and errors keep the same `correlation_id` for traceability.

## Multi-tenant rule
- Every operational entity starts with `tenant_id` when applicable.
- Queries must always be filtered by tenant when listing data.
