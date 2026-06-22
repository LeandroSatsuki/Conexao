# AGENTS

## Objective
Maintain `Preferenza Connector` as a modular, auditable, secure, extensible internal integration platform.

## Mandatory architecture
- Separate connectors, flows, mappings, executions, business rules, and observability.
- No flow may call an external API directly.
- All external access must pass through `BaseConnector` and `ConnectorRegistry`.
- Operational tables must be multi-tenant with `tenant_id` where applicable.
- All integration executions must generate an audit log.
- Duplicate executions with the same idempotency key must be handled as `ignored`, preserving traceability.

## Code standards
- Use FastAPI, SQLAlchemy 2.x, Pydantic v2, and Alembic.
- Prefer small functions, explicit types, and descriptive names.
- Do not hide business rules inside endpoints.
- Keep schemas separate from SQLAlchemy models.

## Security
- Never store credentials in plain text.
- Never log token, password, appkey, client_secret, or bearer token.
- Use `core/encryption.py` for secret encryption and masking.
- Do not expose full credentials through the API.
- Do not use direct Oracle access for Sankhya unless explicitly requested later.

## Tests
- Create and update tests with every functional change.
- Do not call real external APIs in automated tests.
- Cover encryption, masking, idempotency, retry policy, connectors, tenants, flows, mappings, jobs, and the simulated runner when those areas change.
- Do not break existing tests.

## Documentation
- Update README and relevant docs when behavior changes.
- Register decisions in `docs/DECISIONS.md`.
- Update `docs/BACKLOG.md` as the project advances.

## New connectors
- Implement `BaseConnector`.
- Register the connector in `ConnectorRegistry`.
- Create schemas and mock-based tests.
- Document the connector in `docs/CONNECTOR_SDK.md` and, if needed, a dedicated doc.

## Existing behavior changes
- Understand impact before changing public contracts.
- Preserve approved behavior.
- If there is ambiguity, choose conservatively and record it in `docs/DECISIONS.md`.

## Non-regression
- Do not remove approved functionality without explicit authorization.
- Do not delete important documentation without replacement.
- Do not introduce secrets, hardcoded credentials, or real production endpoints.

