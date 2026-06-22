# Project Commands

## Future commands
- `Criar tenant`
- `Listar tenants`
- `Adicionar novo conector`
- `Criar novo fluxo`
- `Adicionar novo endpoint`
- `Criar nova entidade`
- `Corrigir erro de integracao`
- `Adicionar novo mapeamento`
- `Criar teste`
- `Subir versao`

## Local commands
- `docker compose up --build`
- `docker compose up --build api worker`
- `alembic -c alembic.ini upgrade head`
- `pytest`
- `ruff check .`
- `ruff format .`

## Typical API flow
- `Criar tenant` -> `POST /api/v1/tenants`
- `Criar connection` -> `POST /api/v1/connections`
- `Criar flow` -> `POST /api/v1/flows`
- `Criar flow Sankhya read-only` -> `POST /api/v1/flows` with `config_json.operation="sankhya_load_records"`
- `Criar mapping` -> `POST /api/v1/flows/{flow_id}/mappings`
- `Executar flow manual` -> `POST /api/v1/flows/{flow_id}/run`
- `Consultar job` -> `GET /api/v1/jobs/{job_id}`
- `Consultar dead letter` -> `GET /api/v1/jobs/dead-letter?tenant_id=...`
- `Reprocessar job` -> `POST /api/v1/jobs/{job_id}/reprocess`
- `Cancelar job` -> `POST /api/v1/jobs/{job_id}/cancel`
- `Consultar log` -> `GET /api/v1/logs?tenant_id=...`

## Sankhya connection test
- `Teste mock` -> `POST /api/v1/connections/{connection_id}/test?tenant_id=...&mode=mock`
- `Teste real` -> `POST /api/v1/connections/{connection_id}/test?tenant_id=...&mode=real`
- `Read check` -> `POST /api/v1/connections/{connection_id}/test?tenant_id=...&mode=real&read_check=true`

## Sankhya read-only flow
- `Validar fluxo` -> `POST /api/v1/flows/{flow_id}/validate`
- `Executar leitura` -> `POST /api/v1/flows/{flow_id}/run`
- `Consultar logs` -> `GET /api/v1/logs?tenant_id=...`

## Sankhya read-only catalog
- `Listar operações` -> `GET /api/v1/connectors/sankhya/read-operations`
- `Detalhar operação` -> `GET /api/v1/connectors/sankhya/read-operations/{operation_name}`
- `Criar flow catalogado` -> `POST /api/v1/flows` using `sankhya_read_partner`, `sankhya_read_product`, `sankhya_read_seller`, or `sankhya_read_company`

## Worker
- API and worker can be started together with `docker compose up --build`.
- The worker consumes Celery tasks from Redis and processes `sync_job` records asynchronously.
- Use `sync=true` on `POST /api/v1/flows/{flow_id}/run` only for diagnostics or tests.

## Windows
If `make` is unavailable, run the commands above directly in PowerShell.
