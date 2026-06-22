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
- Redis is prepared for queues and async processing.
- Celery is prepared for future background jobs.
- Sankhya is the first connector.
- Manual flow execution is simulated in this stage, with no real external API call.

## Practical decisions
- UUIDs are stored as strings for portability.
- Credentials are persisted encrypted.
- The API returns masked credentials only as metadata.
- Connection tests write technical logs.
- Duplicate flow execution can return an `ignored` job record when the same payload already succeeded.

## Multi-tenant rule
- Every operational entity starts with `tenant_id` when applicable.
- Queries must always be filtered by tenant when listing data.

