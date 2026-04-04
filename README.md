# iadt-processor-hackathon

Microsserviço de análise automatizada de diagramas arquiteturais via IA Generativa — desenvolvido para o desafio **FIAP Secure Systems** (Hackathon IADT).

---

## 1. Descrição do Problema

A **FIAP Secure Systems** demanda um componente de back-end capaz de receber um diagrama de arquitetura de software (enviado como imagem codificada em Base64 ou via URL) e produzir automaticamente uma análise técnica estruturada contendo:

| Campo de Saída | Descrição |
|---|---|
| `componentes_identificados` | Lista de componentes de infraestrutura presentes no diagrama |
| `riscos_arquiteturais` | Lista de vulnerabilidades e pontos de falha detectados |
| `recomendacoes` | Lista de ações corretivas e melhorias propostas |

O output deve ser **determinístico, validado e consumível por outros sistemas** — eliminando respostas em linguagem natural não estruturada geradas diretamente pelo LLM.

---

## 2. Arquitetura Proposta

O sistema segue os princípios da **Clean Architecture**, separando responsabilidades em camadas com dependências que fluem de fora para dentro:

```
┌──────────────────────────────────────────────┐
│  Camada HTTP  (app/api/routes.py)            │  FastAPI · APIRouter
│  Recebe e valida o payload de entrada        │
└─────────────────────┬────────────────────────┘
                      │ DiagramaInput (Pydantic)
┌─────────────────────▼────────────────────────┐
│  Camada Use Case  (app/usecases/)            │  Python puro · sem framework
│  Orquestra a chamada ao "Cérebro de IA"      │
└─────────────────────┬────────────────────────┘
                      │ prompt + imagem
┌─────────────────────▼────────────────────────┐
│  Cérebro de IA  (infrastructure — externa)   │  Gemini Vision + Instructor
│  Única peça que conhece o LLM                │
└─────────────────────┬────────────────────────┘
                      │ AnaliseIAOutput (Pydantic)
┌─────────────────────▼────────────────────────┐
│  Camada de Domínio  (app/domain/schemas.py)  │  Pydantic v2 — contratos puros
└──────────────────────────────────────────────┘
```

### Decisões de Design

| Decisão | Justificativa |
|---|---|
| **FastAPI** | Performance ASGI, validação automática via Pydantic, OpenAPI/Swagger gerado |
| **Clean Architecture** | Regras de negócio isoladas da camada HTTP e do provedor de IA |
| **"Cérebro de IA" isolado** | Toda a interação com o LLM fica em um único ponto (infrastructure), permitindo troca de provedor sem alterar Use Cases ou rotas |
| **Instructor + Pydantic v2** | Força o LLM a retornar JSON estruturado; rejeita automaticamente respostas malformadas |
| **`ConfigDict(frozen=True)`** | O schema de saída é imutável após criação, garantindo integridade dos dados no pipeline |

---

## 3. Fluxo da Solução

```
Cliente (HTTP POST)
       │
       │  { "imagem_base64": "<base64>", "url": "<opcional>" }
       ▼
┌─────────────────┐
│  FastAPI Route  │  Valida payload via DiagramaInput (Pydantic)
│  POST /analyze- │  Rejeita com HTTP 422 se imagem_base64 ausente
│  diagram        │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  AnalisarDiagrama   │  Use Case: orquestra sem conhecer HTTP nem LLM
│  UseCase.execute()  │
└────────┬────────────┘
         │
         ▼
┌───────────────────────────────┐
│  Gemini Vision API            │  Recebe imagem Base64 + prompt estruturado
│  google-generativeai          │  Processa visão computacional no diagrama
└────────┬──────────────────────┘
         │  Resposta raw do LLM
         ▼
┌───────────────────────────────┐
│  Instructor (Structured Output│  Mapeia a resposta para AnaliseIAOutput
│  + Pydantic v2 Validation)    │  Valida tipos, tamanhos e rejeita campos extras
└────────┬──────────────────────┘
         │
         ▼
┌─────────────────┐
│  HTTP 200       │  { "componentes_identificados": [...],
│  JSON Response  │    "riscos_arquiteturais": [...],
└─────────────────┘    "recomendacoes": [...] }
```

---

## 4. Segurança

### 4.1 Guardrails via Pydantic — Mitigação de Alucinações

O schema `AnaliseIAOutput` age como uma **barreira de contrato** entre o LLM e o sistema. Qualquer resposta que não respeite o formato é rejeitada antes de chegar ao cliente:

```python
class AnaliseIAOutput(BaseModel):
    model_config = ConfigDict(frozen=True)           # imutabilidade pós-criação

    componentes_identificados: list[str]
    riscos_arquiteturais: list[Annotated[str, Field(max_length=300)]]  # limite de tamanho
    recomendacoes: list[str]
```

- **Tipo obrigatório `list[str]`**: o LLM não pode devolver texto livre como string única ou objeto aninhado inesperado.
- **`max_length=300` em `riscos_arquiteturais`**: impede que o modelo "alucine" parágrafos inteiros disfarçados de riscos, limitando cada item a uma afirmação objetiva.
- **`frozen=True`**: o objeto de saída não pode ser mutado após validação, protegendo contra modificações acidentais ou maliciosas em pipelines downstream.
- **`str_strip_whitespace=True` na entrada**: remove espaços laterais do payload, prevenindo bypass de validação por whitespace invisible em `DiagramaInput`.

### 4.2 Tratamento de Entradas Não Confiáveis e Controle de Escopo do LLM

| Vetor de Risco | Controle Implementado |
|---|---|
| Payload sem `imagem_base64` | FastAPI retorna HTTP 422 automaticamente (validação Pydantic na entrada) |
| URL arbitrária enviada pelo cliente | Campo `url` é `Optional` e não é executado diretamente; a infraestrutura decide como consumi-lo |
| Prompt injection via conteúdo da imagem | O prompt enviado ao Gemini é **fixo e controlado pelo sistema**; o conteúdo da imagem é tratado como dado visual, não como instrução |
| Resposta do LLM fora do schema | Instructor rejeita e lança exceção antes de qualquer serialização |
| Campos extras injetados pelo LLM | `model_config` padrão do Pydantic v2 ignora campos extras não declarados no schema |

### 4.3 Tratamento de Falhas da IA (Fallback / Retry)

O design da arquitetura suporta as seguintes estratégias de resiliência, a serem implementadas na camada de infrastructure ao integrar o cliente Gemini real:

1. **Retry com backoff exponencial**: Instructor suporta configuração de `max_retries`, reenviando o prompt automaticamente caso o LLM retorne JSON inválido.
2. **Timeout controlado**: o cliente `google-generativeai` aceita timeout por chamada; valores excedidos resultam em exceção propagada como HTTP 504.
3. **Fallback à resposta vazia estruturada**: em caso de falha irrecuperável, o Use Case pode retornar `AnaliseIAOutput` com listas vazias ao invés de propagar erro 500, preservando o contrato de dados.
4. **Isolamento de falha**: como o cliente de IA é injetado no `AnalisarDiagramaUseCase`, substituí-lo por um mock em testes ou por um provedor alternativo (ex.: OpenAI GPT-4o Vision) não altera nenhuma camada superior.

---

## 5. Instruções de Execução

### Pré-requisitos

- Python 3.11+
- Chave de API do Google Gemini (`GOOGLE_API_KEY`)

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

### Variáveis de Ambiente

```bash
# Obrigatória para integração real com Gemini Vision
GOOGLE_API_KEY=<sua-chave-aqui>
```

### Executar o Servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A documentação interativa estará disponível em:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Executar os Testes

```bash
# Suite completa com output detalhado
pytest -v

# Com cobertura de código
pytest -v --tb=short
```

### Exemplo de Requisição

```bash
curl -X POST http://localhost:8000/analyze-diagram \
  -H "Content-Type: application/json" \
  -d '{
    "imagem_base64": "<imagem-codificada-em-base64>",
    "url": "https://example.com/diagrama.png"
  }'
```

**Resposta esperada (HTTP 200):**

```json
{
  "componentes_identificados": ["Load Balancer", "API Gateway", "..."],
  "riscos_arquiteturais": ["Single point of failure no API Gateway..."],
  "recomendacoes": ["Configurar redundância ativa no API Gateway..."]
}
```

---

## 6. Metodologia de Engenharia

### TDD como Garantia do Contrato de Dados

Este projeto adota **Test-Driven Development (TDD)** como metodologia central de qualidade. Os testes não validam apenas o comportamento — eles **especificam e protegem o contrato de dados** que é o coração do sistema.

```
tests/
├── conftest.py          # Fixtures de sessão (TestClient reutilizável)
├── test_routes.py       # Testes de integração: contrato HTTP e schema de resposta
└── test_usecases.py     # Testes unitários: lógica do Use Case isolada do framework
```

#### Cobertura de Cenários

| Teste | Tipo | O que garante |
|---|---|---|
| `test_analyze_diagram_retorna_200_e_schema_correto` | Integração | HTTP 200 + presença das 3 chaves do contrato |
| `test_analyze_diagram_campos_sao_listas` | Integração | Tipos dos campos de saída (nunca string, sempre lista) |
| `test_analyze_diagram_sem_imagem_base64_retorna_422` | Integração | Rejeição de payload inválido na fronteira HTTP |
| `test_analyze_diagram_aceita_url_opcional` | Integração | Campo opcional não quebra o pipeline |
| `test_analisar_diagrama_usecase_retorna_output_esperado` | Unitário | Use Case retorna `AnaliseIAOutput` válido + `max_length` respeitado |

#### Princípio Aplicado

> Os testes foram escritos **antes da implementação** do use case e da rota, garantindo que o design da API seja guiado pela necessidade do consumidor — não pelo que é conveniente implementar. Qualquer regressão no contrato de dados é detectada imediatamente na pipeline de CI.

---

## Stack de Tecnologias

| Tecnologia | Versão mínima | Papel |
|---|---|---|
| `fastapi[standard]` | 0.115.0 | Framework HTTP ASGI |
| `uvicorn[standard]` | 0.29.0 | Servidor ASGI de produção |
| `pydantic` | 2.7.0 | Validação de dados e contratos de schema |
| `instructor` | 1.3.0 | Structured outputs com LLMs (Gemini/OpenAI) |
| `google-generativeai` | 0.7.0 | Cliente oficial da API Gemini Vision |
| `pytest` | 8.2.0 | Framework de testes |
| `pytest-asyncio` | 0.23.0 | Suporte a testes assíncronos |
| `httpx` | 0.27.0 | Cliente HTTP para TestClient do FastAPI |
