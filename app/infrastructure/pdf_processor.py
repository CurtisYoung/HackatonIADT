from __future__ import annotations

import base64

import fitz

def extract_text_and_images_from_pdf(
    pdf_path: str,
) -> list[str | bytes]:
    """Extrai texto e imagens de um arquivo PDF."""
    with fitz.open(pdf_path) as doc:
        content = []
        for page in doc:
            content.append(page.get_text())
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                content.append(image_bytes)
    return content


def process_pdf_and_encode_images(pdf_path: str) -> tuple[str, list[str]]:
    """
    Processa um PDF, extrai texto e converte imagens para base64.

    Retorna uma tupla com o texto extraído e uma lista de imagens em base64.
    """
    with fitz.open(pdf_path) as doc:
        full_text = []
        base64_images = []

        for page in doc:
            full_text.append(page.get_text())

            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                encoded_image = base64.b64encode(image_bytes).decode("utf-8")
                base64_images.append(encoded_image)

    return "\n".join(full_text), base64_images
