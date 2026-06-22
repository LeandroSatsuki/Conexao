# Preferenza Connector

Internal integration platform for Preferenza, starting with Sankhya and prepared for new connectors.

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

## Docker Compose
Start everything with:
```powershell
docker compose up --build
```

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
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/logs?tenant_id=...`

## Typical sequence
1. Create a tenant.
2. Create source and target connections.
3. Create a flow.
4. Create field mappings.
5. Run the flow manually.
6. Inspect the job and logs.

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

