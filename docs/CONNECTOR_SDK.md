# Connector SDK

## Minimum contract
Every connector must implement `BaseConnector`:
- `authenticate()`
- `test_connection()`
- `get_records()`
- `get_record()`
- `create_record()`
- `update_record()`
- `upsert_record()`
- `delete_record()`
- `execute_raw()`
- `get_capabilities()`
- `normalize_error()`

## How to create a new connector
1. Create `backend/app/connectors/<name>/`.
2. Implement the connector client.
3. Define credential and payload schemas.
4. Register the connector in `ConnectorRegistry`.
5. Create mock-based tests.
6. Update the connector-specific documentation.

## Rules
- Do not put flow business rules inside the connector.
- Do not log credentials.
- Do not call the real API in automated tests.

## Sankhya
- Keep the read-only operation catalog and catalog-specific masking close to the connector.
