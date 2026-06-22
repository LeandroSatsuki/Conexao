# Conector Sankhya

## Diretriz principal
O Sankhya deve usar API, gateway ou serviços autorizados. Não usar acesso direto ao Oracle neste projeto.

## MVP atual
- Teste de conexão.
- Autenticação com token ou credenciais.
- Estrutura para consulta e gravação controlada.
- Normalização de erros.
- Log técnico mascarado.

## Credenciais previstas
- `base_url`
- `appkey`
- `token`
- `username`
- `password`
- `client_id`
- `client_secret`
- `environment`

## Regras de segurança
- Não expor token em log.
- Não retornar bearer token pela API.
- Não usar credencial hardcoded.
- Usar credencial criptografada no banco.

