from __future__ import annotations
from __future__ import annotations
import tempfile
from app.domain.repositories import OutputRepository
from app.domain.schemas import AIAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import AIClient
from app.infrastructure.pdf_processor import process_pdf_and_encode_images
import base64

class AnalyzeDiagramUseCase:
    """Orquestra a análise de um diagrama arquitetural via IA.
    """

    def __init__(self, ai_client: AIClient, repository: OutputRepository) -> None:
        self._ai_client = ai_client
        self._repository = repository

    async def execute(self, input_data: DiagramInput) -> AIAnalysisOutput:
        """
        Processa o arquivo (imagem ou PDF), envia para análise e salva o resultado.
        """
        if input_data.file_path.endswith(".pdf"):
            pdf_content = base64.b64decode(input_data.image_base64)
            with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
                temp_pdf.write(pdf_content)
                temp_pdf.seek(0)
                _, base64_images = process_pdf_and_encode_images(temp_pdf.name)
            
            if not base64_images:
                raise ValueError("Nenhuma imagem encontrada no PDF.")
            image_base64 = base64_images[0]
        else:
            image_base64 = input_data.image_base64

        result = await self._ai_client.analyze_image(image_base64)
        await self._repository.save(result)
        return result
