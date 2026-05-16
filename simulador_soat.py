"""
Simulador SOAT — Cliente externo da API de análise de diagramas
===============================================================

Pré-requisitos:
    pip install httpx rich

Como rodar:
    1. Inicie a API em outro terminal:
           uvicorn app.main:app --reload

    2. Execute este script:
           python simulador_soat.py

    3. Para analisar uma imagem diferente, passe o caminho como argumento:
           python simulador_soat.py caminho/para/diagrama.png
"""

from __future__ import annotations

import os
import base64
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

load_dotenv()

API_URL = "https://iadt.matheuslucena.dev/analyze-diagram"
DEFAULT_IMAGE = Path(__file__).parent / "architecture.png"
console = Console()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    console.print("[bold yellow]Aviso:[/bold yellow] API_KEY não encontrada no ambiente ou .env")


def load_image_base64(image_path: Path) -> str:
    """Lê um arquivo de imagem local e retorna sua string codificada em base64."""
    if not image_path.exists():
        console.print(f"[bold red]Erro:[/bold red] Imagem não encontrada: {image_path}")
        sys.exit(1)
    
    # Comprime a imagem localmente antes de codificar (max 3MB)
    from app.core.validation import compress_image_if_needed
    try:
        content = compress_image_if_needed(image_path.read_bytes())
    except Exception as e:
        console.print(f"[dim yellow]Aviso: não foi possível comprimir a imagem ({e}). Usando original.[/dim yellow]")
        content = image_path.read_bytes()
        
    return base64.b64encode(content).decode()


def call_api(image_base64: str) -> dict:
    """Envia o diagrama para a API e retorna a resposta JSON decodificada."""
    payload = {"image_base64": image_base64, "model_type": "bedrock"}

    console.print(Panel(
        f"[cyan]POST[/cyan] {API_URL}\n"
        f"[dim]Payload: image_base64 ({len(image_base64)} chars)[/dim]",
        title="[bold]Simulador SOAT — Enviando requisição[/bold]",
        border_style="blue",
    ))

    with httpx.Client(timeout=120.0) as client:
        response = client.post(API_URL, json=payload, headers={"X-API-Key": API_KEY})

    response.raise_for_status()
    return response.json()


def pretty_print_response(data: dict) -> None:
    """Exibe a resposta da API de forma formatada usando rich."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)

    console.print(Panel(
        syntax,
        title="[bold green]Resposta da API[/bold green]",
        border_style="green",
    ))

    console.print("\n[bold]Resumo:[/bold]")
    console.print(f"  [yellow]Componentes identificados:[/yellow] {len(data.get('identified_components', []))}")
    console.print(f"  [red]Riscos arquiteturais:[/red]    {len(data.get('architectural_risks', []))}")
    console.print(f"  [green]Recomendações:[/green]             {len(data.get('recommendations', []))}")


def main() -> None:
    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IMAGE

    console.print(f"\n[dim]Lendo imagem:[/dim] [bold]{image_path}[/bold]")
    image_base64 = load_image_base64(image_path)

    try:
        data = call_api(image_base64)
    except httpx.ConnectError:
        console.print(Panel(
            "[bold red]Não foi possível conectar à API.[/bold red]\n"
            "Verifique se o servidor está rodando:\n"
            "  [cyan]uvicorn app.main:app --reload[/cyan]",
            border_style="red",
        ))
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        console.print(f"[bold red]Erro HTTP {exc.response.status_code}:[/bold red] {exc.response.text}")
        sys.exit(1)

    pretty_print_response(data)


if __name__ == "__main__":
    main()
