# Sankhya Connector

## Main rule
Sankhya must use authorized API or gateway access only. Direct Oracle access is not allowed in this project.

## Current stage
- Real OAuth 2.0 authentication with `/authenticate` for homologation and production.
- Optional read-only validation using `loadRecords`.
- First asynchronous Sankhya read-only flow is executed through Celery jobs and keeps all payloads masked.
- Mock mode still available for safe local testing.
- Technical logs are masked.
- No write operation is allowed in this stage.
- `DatasetSP.save` is not used.

## Required credentials
- `environment`: `sandbox` or `production`
- `base_url`
- `client_id`
- `client_secret`
- `x_token`
- `auth_mode`: `oauth_client_credentials`
- `timeout_seconds`
- `verify_ssl`

Legacy fields can still be present for compatibility, but the default flow uses OAuth 2.0.

## Authentication flow
1. Decrypt credentials only in memory.
2. Call `POST /authenticate`.
3. Send `client_id`, `client_secret`, and `X-Token`.
4. Receive an access token in memory.
5. Keep the token only for the current execution.
6. Do not persist the token in plain text.

## Read-only test
- `mode=real` on `POST /api/v1/connections/{connection_id}/test` performs real auth.
- `read_check=true` optionally runs a safe read-only `loadRecords` request.
- If `SANKHYA_READ_TEST_ENTITY` or `SANKHYA_READ_TEST_FIELDS` is missing, the endpoint performs auth only.
- The read test is for validation only and does not write any data.

## Read-only flow
- `POST /api/v1/flows/{flow_id}/run` can execute `loadRecords` when `config_json.operation` is `sankhya_load_records`.
- The flow config controls `entity_name`, `fields`, `criteria`, `limit`, and `mode`.
- `mode=mock` uses synthetic data and does not call Sankhya.
- `mode=real` authenticates, calls `loadRecords`, stores `records_count`, and persists only masked samples.

## Error mapping
- `401` -> `authentication_error`
- `403` -> `authorization_error`
- `400` -> `validation_error`
- `429` -> `rate_limit_error`
- `5xx` -> `external_api_error`
- timeout -> `timeout_error`
- anything else -> `unknown_error`

## Safety rules
- Do not expose `client_secret`, `x_token`, bearer token, or access token.
- Do not store tokens in the database.
- Do not log raw sensitive payloads.
- Do not use production by default.
- Do not enable writes in this stage.

## Next step
The next stage is the first read-only Sankhya flow executed asynchronously by a job.
