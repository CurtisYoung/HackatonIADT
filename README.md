# IADT — AI Architecture Diagram Analyzer

Microsserviço de análise automatizada de diagramas arquiteturais via IA Generativa,  
desenvolvido para o desafio **FIAP Secure Systems** (Hackathon IADT).

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

    identified_components: list[str]
    architectural_risks: list[Annotated[str, Field(max_length=300)]]
    recommendations: list[str]
```

Dois `@field_validator` aplicam regras semânticas:

| Guardrail                    | Regra                                                                                           | Exemplo de rejeição          |
|------------------------------|-------------------------------------------------------------------------------------------------|------------------------------|
| `risks_must_be_descriptive`  | Cada risco deve ter **mínimo de 10 palavras** — evita respostas vagas/alucinadas                | `"Security risk."` ❌        |
| `components_must_be_technical` | Nomes genéricos de formas visuais (`box`, `arrow`, `shape`) são rejeitados                   | `["box", "arrow"]` ❌        |

### 4.2 Controles de Segurança Gerais

| Vetor de Risco                          | Controle Implementado                                                                  |
|-----------------------------------------|----------------------------------------------------------------------------------------|
| Payload sem `image_base64`              | FastAPI retorna HTTP 422 automaticamente via validação Pydantic da entrada             |
| Prompt injection via conteúdo da imagem | O prompt enviado ao Gemini é **fixo e controlado pelo sistema** — não interpolado      |
| Resposta do LLM fora do schema          | `AIAnalysisOutput.model_validate_json()` rejeita e dispara o loop de autocorreção     |
| Campos extras injetados pelo LLM        | Pydantic v2 ignora campos extras não declarados no schema por padrão                  |
| Chave de API ausente                    | `GeminiClient.__init__` levanta `ValueError` → rota converte em HTTP 500 descritivo   |
| `frozen=True` no schema de saída        | O objeto de análise não pode ser mutado após validação                                 |

---

## 5. Guia Rápido de Execução

### Pré-requisitos

- Python 3.11+
- Chave de API do Google Gemini (`GEMINI_API_KEY`)

### Instalação

```bash
# Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# Instalar dependências de produção
pip install -r requirements.txt

# Instalar dependências de desenvolvimento (testes)
pip install -r requirements-dev.txt
```

### Configuração do `.env`

Crie um arquivo `.env` na raiz do projeto:

```env
GEMINI_API_KEY=sua_chave_aqui
```

> A chave é carregada pelo `python-dotenv` em `app/main.py` antes de qualquer módulo ser importado.

### Iniciar o Servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa disponível em:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 6. Testes

### Executar a Suíte Completa

```bash
# Todos os testes (pula o teste de integração real se não houver chave)
python -m pytest tests/ -v
```

### Executar apenas testes unitários (sem chamada real à API)

```bash
python -m pytest tests/ -v -k "not usecase_returns_expected"
```

### Cobertura de Testes

| Teste                                              | Tipo        | O que garante                                                    |
|----------------------------------------------------|-------------|------------------------------------------------------------------|
| `test_analyze_diagram_returns_200_and_correct_schema` | Integração | HTTP 200 + presença das 3 chaves do contrato                  |
| `test_analyze_diagram_fields_are_lists`            | Integração  | Tipos dos campos de saída (sempre `list`, nunca `str`)          |
| `test_analyze_diagram_missing_image_base64_returns_422` | Integração | Rejeição de payload inválido na fronteira HTTP               |
| `test_analyze_diagram_accepts_optional_url`        | Integração  | Campo `url` opcional não quebra o pipeline                      |
| `test_analyze_diagram_returns_503_when_ai_unavailable` | Integração | ServerError da API → HTTP 503 semântico para o cliente      |
| `test_usecase_calls_repository_save`               | Unitário    | `repository.save()` é chamado exatamente uma vez com o resultado|
| `test_file_repository_saves_json`                  | Unitário    | `FileOutputRepository` cria arquivo JSON no diretório correto   |
| `test_aianalysisoutput_rejects_vague_risk`         | Guardrail   | Risco com < 10 palavras dispara `ValidationError`               |
| `test_aianalysisoutput_rejects_generic_component`  | Guardrail   | Componente genérico (`box`, `arrow`) dispara `ValidationError`  |
| `test_gemini_client_falls_back_on_retriable_error` | Resiliência | Fallback automático de `gemini-2.5-flash` para `gemini-1.5-flash-8b` em erros 503 |
| `test_analyze_diagram_usecase_returns_expected_output` | Integração real | Chamada real ao Gemini + guardrails aplicados *(requer `GEMINI_API_KEY`)* |

---

## 7. Simulador SOAT

O `simulador_soat.py` simula o cliente externo da equipe SOAT consumindo a API de ponta a ponta.

### Pré-requisito

Servidor rodando em `http://localhost:8000` (ver seção 5).

### Executar com o diagrama padrão (`architecture.png`)

```bash
python simulador_soat.py
```

### Executar com uma imagem customizada

```bash
python simulador_soat.py caminho/para/diagrama.png
```

O simulador imprime o resultado completo formatado no terminal e exibe um resumo com a contagem de componentes, riscos e recomendações identificados.

---

## 8. Stack de Tecnologias

| Tecnologia          | Versão mínima | Papel                                                    |
|---------------------|---------------|----------------------------------------------------------|
| `fastapi[standard]` | 0.115.0       | Framework HTTP ASGI com validação automática             |
| `uvicorn[standard]` | 0.29.0        | Servidor ASGI                                            |
| `pydantic`          | 2.7.0         | Validação de dados, guardrails semânticos e contratos    |
| `google-genai`      | 0.8.0         | SDK nativo do Google Gemini (structured outputs nativos) |
| `python-dotenv`     | 1.0.0         | Carregamento do `.env` com `GEMINI_API_KEY`              |
| `httpx`             | 0.27.0        | Cliente HTTP assíncrono (simulador SOAT + testes)        |
| `pytest`            | 8.2.0         | Framework de testes                                      |
| `pytest-asyncio`    | 0.23.0        | Suporte a testes assíncronos (`asyncio: mode=auto`)      |

