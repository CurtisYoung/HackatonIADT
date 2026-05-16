from __future__ import annotations
import base64
import tempfile
from app.core.validation import detect_mime_from_base64, compress_image_if_needed
from app.domain.repositories import OutputRepository
from app.domain.schemas import SecurityAnalysisOutput, DiagramInput
from app.infrastructure.ai_client import AIClient
from app.infrastructure.pdf_processor import process_pdf_and_encode_images

class SecurityAnalysisUseCase:
    """Orquestra a análise de segurança de um diagrama arquitetural via IA."""

    def __init__(self, ai_client: AIClient, repository: OutputRepository) -> None:
        self._ai_client = ai_client
        self._repository = repository

    async def execute(self, input_data: DiagramInput) -> SecurityAnalysisOutput:
        """Processa o arquivo (imagem ou PDF), envia para análise de segurança e salva o resultado.
        """
        # Se tiver URL, ignora processamento local
        if input_data.image_url:
            result = await self._ai_client.analyze_security(image_url=input_data.image_url)
            return result

        image_base64 = input_data.image_base64

        # Se não tiver base64 mas tiver path, carrega do arquivo
        if not image_base64 and input_data.file_path:
            try:
                with open(input_data.file_path, "rb") as f:
                    content = f.read()
                    # Comprime se for imagem grande
                    if not input_data.file_path.endswith(".pdf"):
                        content = compress_image_if_needed(content)
                    image_base64 = base64.b64encode(content).decode("utf-8")
            except FileNotFoundError:
                raise FileNotFoundError(f"Arquivo não encontrado no servidor: {input_data.file_path}")
            except Exception as e:
                raise RuntimeError(f"Erro ao ler arquivo: {e}")

        if not image_base64:
            raise ValueError("Nenhum conteúdo de imagem fornecido.")

        mime_type, image_base64 = detect_mime_from_base64(image_base64)
        if mime_type == 'application/pdf' or (input_data.file_path and input_data.file_path.endswith('.pdf')):
            pdf_content = base64.b64decode(image_base64)
            with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_pdf:
                temp_pdf.write(pdf_content)
                temp_pdf.seek(0)
                _, base64_images = process_pdf_and_encode_images(temp_pdf.name)
            if not base64_images:
                raise ValueError('Nenhuma imagem encontrada no PDF.')
            image_base64 = base64_images[0]

        result = await self._ai_client.analyze_security(image_base64)
        # await self._repository.save(result)  # Salvar se necessário
        return result
