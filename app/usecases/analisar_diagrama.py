from __future__ import annotations

from app.domain.schemas import AnaliseIAOutput, DiagramaInput


class AnalisarDiagramaUseCase:
    """Orquestra a análise de um diagrama arquitetural via IA.

    A lógica de negócio fica isolada aqui, sem acoplamento direto ao
    framework HTTP ou ao cliente da IA (injetado futuramente via __init__).
    """

    async def execute(self, entrada: DiagramaInput) -> AnaliseIAOutput:
        """Processa a entrada e retorna a análise estruturada.

        Por ora retorna um mock estático para validar o contrato da rota.
        A integração real com Gemini Vision será adicionada na camada
        infrastructure e injetada nesta classe.
        """
        # TODO: substituir pelo cliente Gemini real (infrastructure layer)
        return AnaliseIAOutput(
            componentes_identificados=[
                "Load Balancer",
                "API Gateway",
                "Serviço de Autenticação",
                "Banco de Dados PostgreSQL",
                "Cache Redis",
            ],
            riscos_arquiteturais=[
                "Single point of failure no API Gateway sem configuração de HA.",
                "Ausência de circuit breaker entre serviços pode propagar falhas.",
                "Banco de dados sem réplica de leitura identificada no diagrama.",
            ],
            recomendacoes=[
                "Configurar redundância ativa no API Gateway (mínimo 2 instâncias).",
                "Implementar padrão Circuit Breaker com Resilience4j ou equivalente.",
                "Adicionar réplica de leitura ao PostgreSQL para escalar consultas.",
            ],
        )
