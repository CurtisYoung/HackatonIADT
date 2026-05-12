# IADT — AI Architecture Diagram Analyzer

Microsserviço de análise automatizada de diagramas arquiteturais via IA Generativa,
relacionado à aplicação prática com o Frameworke socio-orientado de TI (F.S.O.)

> **Convenção de código:** todo o código-fonte está em **Inglês**; comentários, docstrings e esta documentação estão em **Português (pt-BR)**.

---

## 1. Visão Geral

O sistema recebe um diagrama de arquitetura de software (imagem codificada em Base64) e produz automaticamente uma análise técnica estruturada com três campos:

| Campo de Saída            | Descrição                                                         |
|---------------------------|-------------------------------------------------------------------|
| `identified_components`   | Componentes de infraestrutura identificados no diagrama           |
| `architectural_risks`     | Vulnerabilidades, pontos de falha e riscos de segurança detectados |
| `recommendations`         | Ações corretivas e melhorias propostas                            |

O output é **determinístico, validado por Pydantic e consumível diretamente por outros sistemas** — eliminando respostas em linguagem natural não estruturada.

---

## 2. Arquitetura

O projeto segue os princípios da **Clean Architecture**, com dependências fluindo sempre de fora para dentro:

```
┌──────────────────────────────────────────────────────┐
│  Camada HTTP   app/api/routes.py                     │  FastAPI · APIRouter
│  Valida o payload de entrada e trata exceções        │
└────────────────────────┬─────────────────────────────┘
                         │ DiagramInput (Pydantic)
┌────────────────────────▼─────────────────────────────┐
│  Caso de Uso   app/usecases/analyze_diagram.py       │  Python puro · sem framework
│  Orquestra cliente de IA + persistência              │
└──────────────┬──────────────────────┬────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌───────────────────────────┐
│  Cliente de IA       │  │  Repositório de Saída      │
│  infrastructure/     │  │  infrastructure/           │
│  ai_client.py        │  │  file_repository.py        │
│  Gemini Vision API   │  │  Salva JSON em             │
│  google-genai SDK    │  │  data/outputs/             │
└──────────────┬───────┘  └───────────────────────────┘
               │ AIAnalysisOutput (Pydantic)
┌──────────────▼───────────────────────────────────────┐
│  Domínio   app/domain/                               │
│  schemas.py · repositories.py  (contratos puros)    │
└──────────────────────────────────────────────────────┘
```

### Padrão Repository

O `AnalyzeDiagramUseCase` recebe um `OutputRepository` por injeção de dependência. A implementação concreta `FileOutputRepository` persiste cada análise como um arquivo JSON com timestamp UTC em `data/outputs/`:

```
data/outputs/
└── analysis_20260425_160248_980144.json
```

Isso garante rastreabilidade completa de todas as análises realizadas, sem acoplamento entre o caso de uso e o mecanismo de armazenamento.

---

## 3. Pipeline de IA e Resiliência

```
Requisição HTTP
      │
      ▼
AIClient.analyze_image()
      │
      ├─► Tenta: Claude-3-Sonnet (Bedrock)  ──► sucesso ──► retorna AIAnalysisOutput
      │         │
      │         └─► falha (429 / 500 / 503 / 504)
      │                   │
      └─► Fallback:  Gemini 2.5 Flash  ──► sucesso ──► retorna AIAnalysisOutput
                          │
                          └─► falha ──► ServerError/ClientError propagado
                                            │
                                            ▼
                                    HTTP 503 para o cliente
```

| Etapa               | Detalhe                                                                                                      |
|---------------------|--------------------------------------------------------------------------------------------------------------|
| **Modelo principal**| `anthropic.claude-3-5-haiku-20240307-v1:0` (Bedrock) — modelo eficiente e atual com boa capacidade de análise |
| **Modelo fallback** | `gemini/gemini-2.5-flash` (Gemini) — acionado nos códigos de erro `429`, `500`, `503`, `504`                |
| **Loop de autocorreção (re-ask)** | Se o output do LLM falhar nos guardrails do Pydantic, o erro de validação é reenviado ao modelo como instrução de correção. Até `_MAX_RETRIES = 2` tentativas por modelo. |
| **Tratamento de erros HTTP** | `ServerError` e `ClientError` são capturados na rota e convertidos em `HTTPException` com código semântico (503 ou 500). |

---

## 4. Segurança e Guardrails

### 4.1 Validação Semântica via Pydantic

O schema `AIAnalysisOutput` age como uma **barreira de contrato** entre o LLM e o sistema:

```python
class AIAnalysisOutput(BaseModel):
    model_config = ConfigDict(frozen=True)           # imutável após criação

    identified_components: list[IdentifiedComponent]
    architectural_risks: list[ArchitecturalRisk]
    recommendations: list[Recommendation]
```

Dois `@field_validator` aplicam regras semânticas:

| Guardrail                    | Regra                                                                                           | Exemplo de rejeição          |
|------------------------------|-------------------------------------------------------------------------------------------------|------------------------------|
| `risks_must_be_descriptive`  | Cada risco deve ter **mínimo de 5 palavras** — evita respostas vagas/alucinadas                | "Security risk." (2 palavras)
| `recommendations_must_be_simple` | As recomendações devem conter no mínimo 5 palavras                                          | "Fix security." (2 palavras)
| `too_generic_components`     | Componentes não devem ser genéricos como "box", "arrow", "circle", "text"                  | "box", "arrow"

### 4.2 Validação de Modelos

O schema valida o modelo de entrada com os parâmetros específicos:

- **Modelo principal:** `anthropic.claude-3-sonnet-20240229-v1` (Bedrock)
- **Modelo fallback:** `gemini/gemini-2.5-flash` (Gemini)

Até 2 tentativas por modelo antes de propagar o erro.

---

## 5. Execução Local (Sem Docker)

Para executar o projeto localmente sem Docker, siga estas etapas:

### 5.1 Pré-requisitos

- Python 3.12 ou superior
- Redis (pode ser executado via Docker ou localmente)
- Git

### 5.2 Configuração do Ambiente

1. **Clone o repositório e instale dependências:**

   ```bash
   git clone https://github.com/CurtisYoung/HackatonIADT.git
   cd HackatonIADT
   pip install -r requirements.txt
   ```

2. **Configure variáveis de ambiente:**

   Copie o arquivo de exemplo e edite com suas credenciais:

   ```bash
   cp .env.example .env
   ```

   Edite o `.env` com suas chaves de API:

   ```bash
   # Credenciais AWS obrigatórias para Bedrock (modelo principal)
   AWS_ACCESS_KEY_ID=your-aws-access-key-id
   AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
   AWS_REGION=us-east-1
   
   # Chave opcional para Gemini (fallback)
   GEMINI_API_KEY=your-gemini-api-key-here
   
   # Chave de API para autenticação (opcional, padrão: "default-secret-key")
   API_KEY=your-api-key-for-auth
   ```

3. **Inicie o Redis:**

   Opção 1: Usando Docker (recomendado):
   ```bash
   docker run -d -p 6379:6379 redis:alpine
   ```

   Opção 2: Instalação local:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   sudo systemctl start redis-server
   
   # macOS com Homebrew
   brew install redis
   brew services start redis
   ```

### 5.3 Executando a Aplicação

1. **Inicie o servidor REST API (FastAPI):**

    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

2. **Inicie o servidor MCP (opcional):**

    ```bash
    python -m app.mcp_server.main
    # Ou diretamente via FastMCP:
    uvicorn app.mcp_server.server:mcp --host 0.0.0.0 --port 8001
    ```

3. **Acesse a API:**

    - API: `http://localhost:8000`
    - Documentação interativa: `http://localhost:8000/docs`
    - Documentação Redoc: `http://localhost:8000/redoc`
    - Health check: `http://localhost:8000/health`
    - MCP Server (standalone): `http://localhost:8001/mcp` (se iniciado)

### 5.4 Executando Testes

```bash
# Executar todos os testes
pytest tests/

# Executar testes específicos
pytest tests/test_routes.py
pytest tests/test_async_routes.py

# Executar testes com coverage
pytest --cov=app tests/
```

### 5.5 Exemplo de Uso com curl

```bash
# Health check
curl -X GET "http://localhost:8000/health"

# Análise síncrona (com API key)
curl -X POST "http://localhost:8000/analyze/diagram/sync" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEElEQVR42mWQMQ7AIAwEwD/gwqJTcWKP1P83s62FI7HUWhtpsA8ec57khkQG0RAbCME4JV6n48u/PDwAQIi3zoQeW7k+i4j13AAAAABJRU5ErkJggg=="
  }'
```

## 6. Execução Local com Docker

Para executar o projeto localmente com Docker, siga estas etapas:

1. **Configurando o ambiente**

   - Crie um arquivo `.env` com suas credenciais:

     ```bash
     mv .env.example .env
     ```

      Edite o `.env` com suas chaves de API reais:

      ```bash
      AWS_ACCESS_KEY_ID=your-aws-access-key-id
      AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
      AWS_REGION=us-east-1
      GEMINI_API_KEY=your-gemini-api-key
      ```

2. **Construindo e executando com Docker Compose**

   ```bash
   # Construir e iniciar os contêineres
   docker-compose up --build
   
   # Para rodar em modo daemon (em segundo plano)
   docker-compose up -d
   ```

3. **Acessando a API**

   - A API está acessível em `http://localhost:8000`
   - Documentação interativa (Swagger UI): `http://localhost:8000/docs`
   - API docs (Redoc): `http://localhost:8000/redoc`

4. **Parando os contêineres**

   ```bash
   docker-compose down
   ```

5. **Executando testes**

   ```bash
   # Simular com o teste de requisitos
   docker-compose exec app python -m pytest
   ```

6. **Limpando recursos**

   ```bash
   # Parar e remover contêineres
   docker-compose down --volumes
  
   # Remover a imagem construída
   docker image rm iadt-app:latest
   ```

---

## 8. Infraestrutura (Terraform)

O projeto inclui arquivos Terraform para provisionar automaticamente o usuário IAM com as permissões necessárias para o Amazon Bedrock.

### 8.1 Provisionamento

1.  Navegue até a pasta terraform:
    ```bash
    cd terraform
    ```
2.  Inicialize o Terraform:
    ```bash
    terraform init
    ```
3.  Aplique a configuração:
    ```bash
    terraform apply
    ```

### 8.2 Obtendo as Credenciais (Secrets)

Como as chaves de acesso são informações sensíveis, elas são marcadas como `sensitive` no Terraform. Para visualizá-las e configurar seu arquivo `.env`, utilize os seguintes comandos:

-   **AWS Access Key ID:**
    ```bash
    terraform output -raw access_key_id
    ```
-   **AWS Secret Access Key:**
    ```bash
    terraform output -raw secret_access_key
    ```
-   **Região AWS:**
    ```bash
    terraform output -raw region
    ```

Copie esses valores para as variáveis correspondentes no seu arquivo `.env`.

---

## 10. Uso como MCP Server (VS Code / Claude Desktop)

Este projeto implementa o **Model Context Protocol (MCP)**, permitindo que IAs como o Claude (no Desktop ou via extensões no VS Code) utilizem as ferramentas de análise de diagrama diretamente.

### 10.1 Executando o Servidor MCP

O servidor MCP é um processo separado que se comunica com a API REST:

```bash
# Terminal 1: API REST
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: MCP Server
python -m app.mcp_server.main
```

**Variáveis de ambiente (opcionais):**
- `MCP_PORT` — Porta do servidor MCP (padrão: `8001`)

O MCP lê `IADT_API_URL` e `API_KEY` automaticamente do `.env`.

### 10.2 Configuração no VS Code (extensão Cline / Roo Code)

Se você utiliza extensões como **Cline** ou **Roo Code** no VS Code:

```json
{
  "mcpServers": {
    "diagram-analyzer": {
      "url": "http://localhost:8001/mcp",
      "env": {
        "IADT_API_URL": "http://localhost:8000",
        "API_KEY": "your-api-key-for-auth"
      }
    }
  }
}
```

### 10.3 Configuração no Claude Desktop

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "diagram-analyzer": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

### 10.4 Ferramentas Disponíveis

- `analyze_diagram`: Analisa componentes e riscos de um arquivo local ou base64.
- `analyze_security`: Foca especificamente em vulnerabilidades de segurança.

### 10.5 Testando o MCP

```bash
# Lista ferramentas
curl -X POST "http://localhost:8001/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'

# Chama a ferramenta analyze_diagram
curl -X POST "http://localhost:8001/mcp" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/call",
    "params": {
      "name": "analyze_diagram",
      "arguments": {"file_path": "architecture.png"}
    }
  }'
```

---

## 10. Tudo pronto! Bora usar o sistema

O sistema está pronto para análise de diagramas arquiteturais!

Faça um pedido POST para `http://localhost:8000/analyze-diagram` com o corpo JSON:

```json
{
  "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAEElEQVR42mWQMQ7AIAwEwD/gwqJTcWKP1P83s62FI7HUWhtpsA8ec57khkQG0RAbCME4JV6n48u/PDwAQIi3ZoQeW7k+i4j13AAAAABJRU5ErkJggg=="
}
```

Veja os outputs validados na resposta e os arquivos JSON salvos em `data/outputs/`.