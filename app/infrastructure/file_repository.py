from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.domain.repositories import OutputRepository
from app.domain.schemas import AIAnalysisOutput

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "outputs"


class FileOutputRepository(OutputRepository):
    """Persiste os resultados de análise de IA como arquivos JSON em data/outputs/.

    Cada resultado salvo recebe seu próprio arquivo nomeado com um timestamp UTC,
    retendo todo o histórico de análises de forma auditável.

    Formato do arquivo: analysis_<YYYYMMDD_HHMMSS_ffffff>.json
    """

    def __init__(self, output_dir: Path = _OUTPUT_DIR) -> None:
        self._output_dir = output_dir

    async def save(self, result: AIAnalysisOutput) -> None:
        """Serializa o resultado em JSON e o grava em disco.

        O diretório é criado automaticamente se não existir.
        A gravação é delegada a um pool de threads para que o loop de
        eventos assíncrono nunca seja bloqueado por operações de I/O.
        """
        await asyncio.to_thread(self._write, result)

    def _write(self, result: AIAnalysisOutput) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        file_path = self._output_dir / f"analysis_{timestamp}.json"
        file_path.write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )
