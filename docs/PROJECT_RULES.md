# Project Rules

## Fixed rules
- The platform must be multi-tenant.
- No credential may be stored in plain text.
- No credential may be fully exposed through the API.
- No secret may appear in logs.
- No flow may access an external API outside a connector.
- Sankhya must use authorized API or gateway access only, never direct Oracle access in this project.

## Operational rules
- Every execution must be traceable.
- Every error must be classified.
- Reprocessing must preserve history.
- Duplicates must be prevented with idempotency.
- Temporary errors can be retried with control.
- Duplicate payloads must return `ignored` handling and keep the idempotency key.
- `pending` jobs are created before asynchronous processing.
- `running` jobs must not be force-killed without an explicit operational decision.
- `cancel_requested` is the safe signal for a running job when supported.
- `dead_letter` is the terminal state for exhausted retries.
- A tenant with linked connections, flows, jobs, or logs cannot be deleted.
- An inactive flow cannot execute.

## MVP decisions
- Auto-create a tenant when a new connection is created.
- Register only Sankhya as a connector in the MVP.
- Expose only the initial connection, logs, jobs, flows, mappings, tenants, and health endpoints.
- Do not implement a frontend in the MVP.
