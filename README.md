# Preferenza Connector

Internal integration platform for Preferenza, starting with Sankhya and prepared for new connectors.

The current recommended operating mode is **on-demand**. The platform does not need to stay online 24/7 for the current stage. A continuous service mode remains available for future growth, scheduled work, or monitoring needs.

## Stack
- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery
- Pytest
- HTTPX
- Docker and Docker Compose

## How to run locally
1. Create `.env` from `.env.example`.
2. Start infrastructure:
   ```powershell
   docker compose up -d postgres redis
   ```
3. Install backend dependencies:
   ```powershell
   cd backend
   pip install -r requirements.txt
   ```
4. Run migrations:
   ```powershell
   alembic -c alembic.ini upgrade head
   ```
5. Start the API:
   ```powershell
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
6. Start the worker if you are not using Docker Compose:
   ```powershell
   celery -A app.workers.tasks.celery_app worker --loglevel=INFO --concurrency=1
   ```

## Docker Compose
Start everything with:
```powershell
docker compose up --build
```
The compose stack starts:
- `api`
- `postgres`
- `redis`
- `worker`

On-demand operation is the preferred path for the current stage:
- Start the stack when needed.
- Run migrations.
- Run validation or integration.
- Review the report and logs.
- Stop the stack.

The service mode remains supported by the same stack if the project later needs continuous operation.

## Main endpoints
- `POST /api/v1/tenants`
- `GET /api/v1/tenants`
- `GET /api/v1/tenants/{tenant_id}`
- `PATCH /api/v1/tenants/{tenant_id}`
- `DELETE /api/v1/tenants/{tenant_id}`
- `GET /api/v1/health`
- `GET /api/v1/connectors`
- `POST /api/v1/connections`
- `GET /api/v1/connections?tenant_id=...`
- `POST /api/v1/connections/{connection_id}/test?tenant_id=...`
- `POST /api/v1/flows`
- `GET /api/v1/flows?tenant_id=...`
- `GET /api/v1/flows/{flow_id}`
- `PATCH /api/v1/flows/{flow_id}`
- `DELETE /api/v1/flows/{flow_id}`
- `POST /api/v1/flows/{flow_id}/mappings`
- `GET /api/v1/flows/{flow_id}/mappings`
- `PATCH /api/v1/mappings/{mapping_id}`
- `DELETE /api/v1/mappings/{mapping_id}`
- `POST /api/v1/flows/{flow_id}/run`
- `GET /api/v1/jobs?tenant_id=...`
- `GET /api/v1/jobs/dead-letter?tenant_id=...`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `POST /api/v1/jobs/{job_id}/reprocess`
- `GET /api/v1/logs?tenant_id=...`

## Typical sequence
1. Create a tenant.
2. Create source and target connections.
3. Create a flow.
4. Create field mappings.
5. Run the flow manually.
6. Inspect the job and logs.
7. Reprocess dead-letter jobs when necessary.

## Async execution
- `POST /api/v1/flows/{flow_id}/run` creates a `pending` job and enqueues a Celery task.
- `sync=true` can be used to execute the same job synchronously in test or diagnostic scenarios.
- Retryable failures move through `retrying` and eventually `dead_letter`.
- `POST /api/v1/jobs/{job_id}/reprocess` resets a `failed` or `dead_letter` job for another attempt.
- `POST /api/v1/jobs/{job_id}/cancel` cancels `pending` jobs and marks `running` jobs with `cancel_requested`.
- Every attempt writes an `integration_log` and classified failures write an `integration_error`.
- `GET /api/v1/jobs/dead-letter?tenant_id=...` lists jobs waiting for manual recovery.
- Each execution uses a unique `correlation_id` shared by the job, logs, and errors.

## Sankhya connection test
- `POST /api/v1/connections/{connection_id}/test?tenant_id=...&mode=mock` keeps the simulated path.
- `mode=real` runs OAuth 2.0 `POST /authenticate` against the configured Sankhya environment.
- `read_check=true` optionally runs a read-only `loadRecords` validation after auth.
- No token, secret, or X-Token is returned by the API or written to logs.
- This stage does not write any data to Sankhya and does not use `DatasetSP.save`.

## Sankhya read-only flow
- Create the flow with `config_json.operation = "sankhya_load_records"`.
- Configure `config_json.entity_name`, `config_json.fields`, `config_json.limit`, and `config_json.mode`.
- `POST /api/v1/flows/{flow_id}/run` enqueues a Celery job that authenticates and calls `loadRecords` in read-only mode.
- The worker stores masked `source_payload`, `transformed_payload`, `response_payload`, `records_count`, logs, and errors.
- This stage still does not write any data to Sankhya and still does not use `DatasetSP.save`.

## Sankhya read-only catalog
- `GET /api/v1/connectors/sankhya/read-operations` lists the controlled read-only operations.
- `GET /api/v1/connectors/sankhya/read-operations/{operation_name}` shows the details of one operation.
- Cataloged operations are safer than the advanced `sankhya_load_records` mode because they pin allowed fields, default fields, limits, and masking rules.
- Cataloged read-only operations are blocked from production by default.
- The advanced `sankhya_load_records` mode remains available for compatibility and manual tuning.

## Sankhya homologation validation
- Set `SANKHYA_BASE_URL`, `SANKHYA_CLIENT_ID`, `SANKHYA_CLIENT_SECRET`, and `SANKHYA_X_TOKEN` before running the validation script.
- Run `python backend/scripts/validate_sankhya_readonly.py`.
- The script validates the API, creates or reuses a tenant and Sankhya connection, creates the cataloged read-only flows, runs them through Celery, polls the jobs, and writes a sanitized JSON report under `backend/reports/`.
- Generated reports are ignored by git and do not include raw tokens or secrets.
- Before any future Sankhya write stage, this validation must be executed and approved.

## Operational flow
1. Create a tenant.
2. Create source and target connections.
3. Create a flow.
4. Create field mappings.
5. Run the flow manually.
6. Inspect the job status and execution logs.
7. Reprocess `failed` or `dead_letter` jobs when needed.
8. Cancel pending work when the execution should not continue.

## Tests
Run tests from `backend`:
```powershell
cd backend
pytest
```

## Useful commands
- `alembic -c alembic.ini upgrade head`
- `pytest`
- `ruff check .`
- `ruff format .`
- `docker compose up --build`
- `docker compose up --build api worker`
- `python backend/scripts/validate_sankhya_readonly.py`
- `.\scripts\start_on_demand.ps1`
- `.\scripts\run_sankhya_validation.ps1`
- `.\scripts\status.ps1`
- `.\scripts\stop_on_demand.ps1`
