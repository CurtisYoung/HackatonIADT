"""Utilities for input validation.

Este módulo contém funções auxiliares para validar o conteúdo enviado ao serviço.
Atualmente inclui deteção simples de tipo MIME baseada em assinaturas de arquivos
para evitar upload de arquivos maliciosos ou inesperados.
"""
import base64
import binascii

def detect_mime_from_base64(b64_string: str) -> str:
    """Retorna o tipo MIME detectado a partir de uma string Base64.

    Suporta JPEG, PNG e PDF. Levanta ``ValueError`` se o tipo não for reconhecido.
    """
    try:
        raw = base64.b64decode(b64_string, validate=True)
    except binascii.Error as exc:
        raise ValueError('Base64 inválido') from exc

    # JPEG magic numbers: FF D8 FF
    if raw.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    # PNG magic numbers: 89 50 4E 47 0D 0A 1A 0A
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    # PDF magic: %PDF-
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    raise ValueError('Tipo de arquivo não suportado. Apenas JPEG, PNG ou PDF são aceitos')
