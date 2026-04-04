from __future__ import annotations

from fastapi.testclient import TestClient


ENDPOINT = "/analyze-diagram"

PAYLOAD_VALIDO: dict[str, str] = {
    "imagem_base64": "aW1hZ2VtX2Zha2VfYmFzZTY0",
}

CHAVES_ESPERADAS: frozenset[str] = frozenset(
    {"componentes_identificados", "riscos_arquiteturais", "recomendacoes"}
)


def test_analyze_diagram_retorna_200_e_schema_correto(client: TestClient) -> None:
    """POST /analyze-diagram com payload válido deve retornar HTTP 200 e
    um JSON contendo exatamente as chaves definidas em AnaliseIAOutput."""
    response = client.post(ENDPOINT, json=PAYLOAD_VALIDO)

    assert response.status_code == 200

    corpo = response.json()
    assert CHAVES_ESPERADAS.issubset(corpo.keys()), (
        f"Chaves ausentes na resposta: {CHAVES_ESPERADAS - corpo.keys()}"
    )


def test_analyze_diagram_campos_sao_listas(client: TestClient) -> None:
    """Todos os campos do schema de saída devem ser listas."""
    response = client.post(ENDPOINT, json=PAYLOAD_VALIDO)
    corpo = response.json()

    for chave in CHAVES_ESPERADAS:
        assert isinstance(corpo[chave], list), (
            f"Campo '{chave}' deveria ser uma lista, mas é {type(corpo[chave])}"
        )


def test_analyze_diagram_sem_imagem_base64_retorna_422(client: TestClient) -> None:
    """Payload sem o campo obrigatório imagem_base64 deve retornar HTTP 422."""
    response = client.post(ENDPOINT, json={})

    assert response.status_code == 422


def test_analyze_diagram_aceita_url_opcional(client: TestClient) -> None:
    """O campo url é opcional; enviá-lo não deve alterar o status_code."""
    payload = {**PAYLOAD_VALIDO, "url": "https://example.com/diagrama.png"}
    response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 200
