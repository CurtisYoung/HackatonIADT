# Arquitetura - Microsserviço de Processamento de IA (IADT)

## Objetivo
Receber um payload contendo um diagrama de arquitetura (em base64 ou URL), processar essa imagem usando a API do Gemini Vision e devolver um JSON estruturado contendo a análise arquitetural, de risco e recomendações.

## Estrutura de Pastas Esperada
- `app/`
  - `domain/`: Modelos Pydantic (Entrada da API e Saída Estruturada do LLM).
  - `usecases/`: Lógica orquestradora (Recebe a imagem, chama o agente de IA, valida).
  - `infrastructure/`: Clientes externos (Integração com a SDK `google-generativeai`).
  - `api/`: Rotas do FastAPI.

## Contratos de Dados (Guardrails)
A integração com o LLM não deve retornar texto livre. Deve-se garantir que o JSON retornado pela IA atenda ao seguinte schema de saída:
- `componentes_identificados`: Lista de strings.
- `riscos_arquiteturais`: Lista de strings detalhando riscos baseados no diagrama.
- `recomendacoes`: Lista de ações mitigadoras sugeridas.

## Tratamento de Falhas
- Implementar Retry Pattern simples caso a IA retorne um JSON inválido (parsing error do Pydantic).
- Logar erros de comunicação com a API do Gemini de forma estruturada.