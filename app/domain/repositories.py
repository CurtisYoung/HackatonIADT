from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.schemas import AIAnalysisOutput


class OutputRepository(ABC):
    """Contrato abstrato para persistência dos resultados de análise da IA.

    As implementações podem armazenar dados em qualquer meio
    (sistema de arquivos, banco de dados, armazenamento de objetos, etc.) sem
    que as camadas de domínio ou de casos de uso conheçam os detalhes.
    """

    @abstractmethod
    async def save(self, result: AIAnalysisOutput) -> None:
        """Persiste um resultado de análise validado.

        Args:
            result: O resultado validado da análise de IA a ser armazenado.
        """
