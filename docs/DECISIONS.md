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

