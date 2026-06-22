# Project Commands

## Future commands
- `Criar tenant`
- `Listar tenants`
- `Adicionar novo conector`
- `Criar novo fluxo`
- `Adicionar novo endpoint`
- `Criar nova entidade`
- `Corrigir erro de integração`
- `Adicionar novo mapeamento`
- `Criar teste`
- `Subir versão`

## Local commands
- `docker compose up --build`
- `alembic -c alembic.ini upgrade head`
- `pytest`
- `ruff check .`
- `ruff format .`

## Typical API flow
- `Criar tenant` -> `POST /api/v1/tenants`
- `Criar connection` -> `POST /api/v1/connections`
- `Criar flow` -> `POST /api/v1/flows`
- `Criar mapping` -> `POST /api/v1/flows/{flow_id}/mappings`
- `Executar flow manual` -> `POST /api/v1/flows/{flow_id}/run`
- `Consultar job` -> `GET /api/v1/jobs/{job_id}`
- `Consultar log` -> `GET /api/v1/logs?tenant_id=...`

## Windows
If `make` is unavailable, run the commands above directly in PowerShell.

