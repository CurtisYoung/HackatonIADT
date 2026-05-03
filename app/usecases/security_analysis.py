from __future__ import annotations
from app.domain.repositories import OutputRepository
from app.domain.schemas import SecurityAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import AIClient
import base64
from app.infrastructure.pdf_processor import process_pdf_and_encode_images

class SecurityAnalysisUseCase:
    """Orquestra a análise de segurança de um diagrama arquitetural via IA."""

    def __init__(self, ai_client: AIClient, repository: OutputRepository) -> None:
        self._ai_client = ai_client
        self._repository = repository

    async def execute(self, input_data: DiagramInput) -> SecurityAnalysisOutput:
        """
        Processa o arquivo (imagem ou PDF), envia para análise de segurança e salva o resultado.
        """
        if input_data.file_path.endswith(".pdf"):
            pdf_content = base64.b64decode(input_data.image_base64)
            temp_pdf_path = "temp.pdf"
            with open(temp_pdf_path, "wb") as f:
                f.write(pdf_content)

            _, base64_images = process_pdf_and_encode_images(temp_pdf_path)
            
            if not base64_images:
                raise ValueError("Nenhuma imagem encontrada no PDF.")
            image_base64 = base64_images[0]
        else:
            image_base64 = input_data.image_base64

        result = await self._ai_client.analyze_security(image_base64)
        # O repositório pode precisar ser adaptado para salvar diferentes tipos de output
        # await self._repository.save(result) 
        return result
