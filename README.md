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
GeminiClient.analyze_image()
      │
      ├─► Tenta: gemini-2.5-flash  ──► sucesso ──► retorna AIAnalysisOutput
      │         │
      │         └─► falha (429 / 500 / 503 / 504)
      │                   │
      └─► Fallback:  gemini-1.5-flash-8b  ──► sucesso ──► retorna AIAnalysisOutput
                          │
                          └─► falha ──► ServerError/ClientError propagado
                                            │
                                            ▼
                                    HTTP 503 para o cliente
```

| Etapa               | Detalhe                                                                                                      |
|---------------------|--------------------------------------------------------------------------------------------------------------|
| **Modelo principal**| `gemini-2.5-flash` — melhor capacidade de visão computacional                                                |
| **Modelo fallback** | `gemini-1.5-flash-8b` — econômico e resiliente, acionado nos códigos `429`, `500`, `503`, `504`             |
| **Loop de autocorreção (re-ask)** | Se o output do LLM falhar nos guardrails do Pydantic, o erro de validação é reenviado ao modelo como instrução de correção. Até `_MAX_RETRIES = 2` tentativas por modelo. |
| **Tratamento de erros HTTP** | `ServerError` e `ClientError` do SDK `google-genai` são capturados na rota e convertidos em `HTTPException` com código semântico (503 ou 500). |

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

- **Modelo principal:** `anthropic.claude-3-sonnet-20240229-v1` (pode ser alterado via ambiente)
- **Modelo fallback:** `anthropic.claude-3-haiku-20240307` (pode ser alterado via ambiente)

Até 2 tentativas por modelo antes de propagar o erro.

---

## 5. Execução Local com Docker

Para executar o projeto localmente com Docker, siga estas etapas:

1. **Configurando o ambiente**

   - Crie um arquivo `.env` com suas credenciais:

     ```bash
     mv .env.example .env
     ```

     Edite o `.env` com suas chaves de API reais:

     ```bash
     GEMINI_API_KEY=your-gemini-api-key
     AWS_ACCESS_KEY_ID=your-aws-access-key-id
     AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
     AWS_REGION=us-east-1
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

## 7. Infraestrutura (Terraform)

O projeto inclui arquivos Terraform para provisionar automaticamente o usuário IAM com as permissões necessárias para o Amazon Bedrock.

### 7.1 Provisionamento

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

### 7.2 Obtendo as Credenciais (Secrets)

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

## 9. Uso como MCP Server (VS Code / Claude Desktop)

Este projeto implementa o **Model Context Protocol (MCP)**, permitindo que IAs como o Claude (no Desktop ou via extensões no VS Code) utilizem as ferramentas de análise de diagrama diretamente.

### 9.1 Configuração no VS Code (extensão Cline / Roo Code)

Se você utiliza extensões como **Cline** ou **Roo Code** no VS Code, adicione o servidor MCP nas configurações da extensão:

```json
{
  "mcpServers": {
    "diagram-analyzer": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/caminho/para/o/projeto/HackatonIADT",
      "env": {
        "IADT_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### 9.2 Configuração no Claude Desktop

Para usar com o aplicativo Claude Desktop, adicione o seguinte ao seu arquivo `claude_desktop_config.json`:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "diagram-analyzer": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "C:\\caminho\\para\\o\\projeto\\HackatonIADT",
      "env": {
        "IADT_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### 9.3 Ferramentas Disponíveis

Uma vez configurado, a IA terá acesso às seguintes ferramentas:
- `analyze_diagram`: Analisa componentes e riscos de um arquivo local ou base64.
- `analyze_security`: Foca especificamente em vulnerabilidades de segurança.

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