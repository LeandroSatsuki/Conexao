# SDK de Conectores

## Contrato mínimo
Todo conector deve implementar `BaseConnector`:
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

## Como criar um novo conector
1. Criar `backend/app/connectors/<nome>/`.
2. Implementar o cliente do conector.
3. Definir schemas de credenciais e payloads.
4. Registrar o conector no `ConnectorRegistry`.
5. Criar testes com mock.
6. Atualizar a documentação específica do conector.

## Regras
- Não colocar regra de negócio do fluxo dentro do conector.
- Não logar credenciais.
- Não chamar API real em testes automatizados.

