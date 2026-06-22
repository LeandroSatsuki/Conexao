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
