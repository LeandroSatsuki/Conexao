# Technical Decisions

## 2026-06-22
Date: 2026-06-22
Decision: Store UUIDs as `String(36)` in MVP tables.
Reason: Simplifies compatibility across PostgreSQL, SQLite test runs, and local development.
Impact: Easier initial testing and migrations.
Alternatives considered: Native UUID columns.

Date: 2026-06-22
Decision: Encrypt credentials with Fernet using a key from `.env`.
Reason: Satisfies secret protection with a simple, auditable implementation.
Impact: Requires explicit `FERNET_KEY` configuration.
Alternatives considered: External KMS, hashing, or custom encryption.

Date: 2026-06-22
Decision: Auto-create a tenant when a new connection is created in the MVP.
Reason: There is no tenant onboarding endpoint in the MVP and the platform must be usable immediately.
Impact: Simplifies the first user journey.
Alternatives considered: Require a tenant to be created first.

Date: 2026-06-22
Decision: Implement `SankhyaClient` with `httpx.Client` and injected transport.
Reason: Enables mock-based tests without real API calls.
Impact: Reduces coupling and improves testability.
Alternatives considered: Async client in the MVP.

Date: 2026-06-22
Decision: Return `ignored` handling for duplicate flow payloads while preserving the idempotency key.
Reason: Keeps traceability for repeated submissions without executing the same payload twice.
Impact: The runner records the duplicate attempt and log, while avoiding duplicated downstream processing.
Alternatives considered: Return HTTP 409 or ignore silently.

Date: 2026-06-22
Decision: Block DELETE on tenants and flows when linked resources exist.
Reason: Avoid orphaned history and accidental data loss.
Impact: Requires explicit cleanup or deactivation before deletion.
Alternatives considered: Full soft delete or automatic cascading deletes.

Date: 2026-06-22
Decision: Create jobs as `pending` and hand them to Celery for asynchronous execution.
Reason: Keeps the API responsive and prepares the platform for real background processing.
Impact: The worker becomes responsible for state transitions after enqueueing.
Alternatives considered: Keep the runner synchronous in the API.

Date: 2026-06-22
Decision: Use `attempt_count` and `max_attempts` to drive retry and dead-letter handling.
Reason: Makes retry behavior deterministic and easy to audit.
Impact: Retryable failures can progress to `retrying` and then `dead_letter` without manual intervention.
Alternatives considered: Unlimited retries or implicit broker retry only.

Date: 2026-06-22
Decision: Preserve execution history during reprocessing by creating a new attempt instead of rewriting prior logs.
Reason: Maintains auditability and supports root-cause analysis.
Impact: Reprocess actions create new traceable logs and reuse the flow/job identity only for the recovery operation.
Alternatives considered: Reset the original record in place.

Date: 2026-06-22
Decision: Use `cancel_requested` for running jobs instead of force-stopping the worker task.
Reason: Avoids unsafe termination and keeps state transitions explicit.
Impact: Pending jobs can be cancelled immediately, while running jobs remain consistent.
Alternatives considered: Kill the Celery task directly from the API.

Date: 2026-06-22
Decision: Thread a `correlation_id` through jobs, logs, and errors.
Reason: Improves traceability and prepares the platform for future real integrations.
Impact: Every execution can be traced end-to-end across operational tables.
Alternatives considered: Rely on job IDs only.

Date: 2026-06-22
Decision: Support Sankhya OAuth 2.0 `POST /authenticate` as the default real auth flow.
Reason: This is the current Sankhya recommended model for homologation and production.
Impact: The connector now uses `client_id`, `client_secret`, and `X-Token` and keeps the access token in memory only.
Alternatives considered: Keep the legacy `/login` path as the primary flow.

Date: 2026-06-22
Decision: Keep connection tests read-only and disable writes in this stage.
Reason: The goal is to validate connectivity safely before any business mutation is allowed.
Impact: `mode=real` can authenticate and optionally run `read_check`, but cannot save data.
Alternatives considered: Enable `DatasetSP.save` for early end-to-end testing.

Date: 2026-06-22
Decision: Mask Sankhya secrets with full redaction in Sankhya-specific logs and connection summaries.
Reason: Partial masking still reveals part of the secret and does not meet the current safety bar.
Impact: `client_secret`, `x_token`, bearer token, and access token are rendered as `***` in Sankhya-specific audit data.
Alternatives considered: Reuse the generic partial masking helper for all contexts.

Date: 2026-06-22
Decision: Accept `homologation` as a compatibility alias for `sandbox` in Sankhya credentials.
Reason: Existing test data and local environments still use the legacy label.
Impact: The connector remains compatible while the documented canonical values stay `sandbox` and `production`.
Alternatives considered: Reject any noncanonical environment value.

Date: 2026-06-22
Decision: Store Sankhya read-only flow parameters in `integration_flows.config_json`.
Reason: The first asynchronous Sankhya flow needs technical parameters such as `operation`, `entity_name`, `fields`, `criteria`, `limit`, and `mode` without expanding the core flow columns too early.
Impact: The API can validate and run Sankhya read-only flows without introducing a separate operation table yet.
Alternatives considered: Add dedicated columns for each Sankhya operation parameter.

Date: 2026-06-22
Decision: Execute Sankhya read-only flows without deduplicating by idempotency key.
Reason: Repeated read-only validations should run again so operators can compare fresh ERP state instead of receiving an `ignored` duplicate.
Impact: Read-only Sankhya jobs remain traceable, but repeated executions with the same config are allowed to proceed.
Alternatives considered: Reuse the duplicate suppression used by generic flows.

Date: 2026-06-22
Decision: Persist only a masked sample of Sankhya read-only responses and record `records_count`.
Reason: The flow may return multiple rows, but the platform must avoid storing oversized or sensitive payloads in full.
Impact: The worker keeps auditability while limiting exposure and storage volume.
Alternatives considered: Persist the entire response body unmodified.
