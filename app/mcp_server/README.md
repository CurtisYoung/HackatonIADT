# MCP Server

Este servidor **MCP (Micro‑Control Plane)** disponibiliza as ferramentas `analyze_diagram` e `analyze_security` como rotas customizadas do FastMCP.

## Execução
```bash
# Instale as dependências (já incluídas no requirements.txt)
pip install -r requirements.txt

# Defina a variável de ambiente obrigatória
export API_KEY=seu-token-secreto

# Opcional – URL base da API interna usada pelo MCP
export IADT_API_URL=http://localhost:8000

# Inicie o servidor
python -m app.mcp_server.server
```
O servidor escuta na porta `8001` (ou na porta definida por `MCP_PORT`).

## Autenticação
- **Variável de ambiente** `API_KEY` – token usado para validar chamadas ao MCP. O processo aborta se não estiver definido.
- **Header HTTP** – todas as requisições internas ao servidor da API (ex.: `/analyze/diagram/sync`) enviam o cabeçalho `X-API-Key: $API_KEY`.

## Rotas expostas
| Path | Método | Descrição |
|------|--------|-----------|
| `/health` | `GET` | Verifica se o MCP está ativo. |
| (Ferramentas) `analyze_diagram` | – | Disponível via FastMCP como ferramenta chamada pelos consumidores da API. |
| (Ferramentas) `analyze_security` | – | idem. |

## Configuração do cliente
Exemplo de arquivo JSON que o cliente pode usar para descobrir o MCP e já incluir o token:
```json
{
  "servers": {
    "teste-mcp-server": {
      "url": "https://iadt.matheuslucena.dev/mcp",
      "type": "http",
      "headers": {
        "X-API-Key": "SEU_TOKEN_API_KEY_AQUI"
      }
    }
  },
  "inputs": []
}
```

## Observações
- Não há fallback para `API_KEY`; o servidor falhará ao iniciar caso a variável esteja ausente.
- O servidor delega a análise real a `IADT_API_URL` – ajuste conforme seu ambiente.
