"""Utilities for input validation.

Este módulo contém funções auxiliares para validar o conteúdo enviado ao serviço.
Atualmente inclui deteção simples de tipo MIME baseada em assinaturas de arquivos
para evitar upload de arquivos maliciosos ou inesperados.
"""
import base64
import binascii

import io
from PIL import Image

def compress_image_if_needed(image_bytes: bytes, max_size_mb: float = 3.0) -> bytes:
    """Redimensiona e comprime a imagem se ela exceder o tamanho máximo em MB.
    
    Tenta manter a proporção e reduz a qualidade se necessário.
    """
    if len(image_bytes) <= max_size_mb * 1024 * 1024:
        return image_bytes
    
    img = Image.open(io.BytesIO(image_bytes))
    
    # Se for RGBA (PNG), converte para RGB para JPEG se possível, ou mantém PNG comprimido
    format = img.format or "JPEG"
    if img.mode in ("RGBA", "P") and format == "JPEG":
        img = img.convert("RGB")

    # Reduz dimensões se forem muito grandes (ex: > 4096px)
    max_dim = 3072
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    quality = 85
    img.save(output, format=format, quality=quality, optimize=True)
    
    # Se ainda estiver grande, reduz qualidade agressivamente
    while output.tell() > max_size_mb * 1024 * 1024 and quality > 30:
        quality -= 15
        output = io.BytesIO()
        img.save(output, format=format, quality=quality, optimize=True)
        
    return output.getvalue()


def detect_mime_from_base64(b64_string: str) -> tuple[str, str]:
    """Retorna o tipo MIME detectado e a string Base64 limpa.

    Suporta JPEG, PNG e PDF. Levanta ``ValueError`` se o tipo não for reconhecido.
    """
    cleaned_b64 = b64_string
    # Remove prefixo data:image/...;base64, se presente
    if b64_string.startswith('data:'):
        # Extrai a parte após base64,
        parts = b64_string.split(',', 1)
        if len(parts) != 2:
            raise ValueError('Formato data URL inválido')
        cleaned_b64 = parts[1]
    
    try:
        # Decodifica apenas o início para identificar o tipo (máx 32 bytes decodificados)
        # Base64 encoding ratio é 4:3, então ~44 caracteres base64 dão ~33 bytes.
        sample = base64.b64decode(cleaned_b64[:64], validate=False)
    except binascii.Error as exc:
        raise ValueError('Base64 inválido') from exc

    # JPEG magic numbers: FF D8 FF
    if sample.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg", cleaned_b64
    # PNG magic numbers: 89 50 4E 47 0D 0A 1A 0A
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", cleaned_b64
    # PDF magic: %PDF-
    if sample.startswith(b"%PDF-"):
        return "application/pdf", cleaned_b64
    raise ValueError('Tipo de arquivo não suportado. Apenas JPEG, PNG ou PDF são aceitos')
