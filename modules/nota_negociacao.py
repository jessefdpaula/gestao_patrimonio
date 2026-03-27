"""
Módulo para leitura e extração de dados de Notas de Negociação em PDF.

Delega para o sistema de parsers em modules/parsers/.
Para adicionar suporte a uma nova corretora, veja modules/parsers/__init__.py.

Dependências: pypdf
"""

from pathlib import Path
from .parsers import get_parser_nota, listar_parsers_nota

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader


def ler_nota_pdf(caminho_pdf: str) -> dict:
    """
    Lê uma nota de negociação em PDF e extrai as operações.

    Retorna:
        {
            "numero_nota": str,
            "data_pregao": str (AAAA-MM-DD),
            "corretora": str,
            "parser_usado": str,
            "operacoes": [ {ticker, tipo, quantidade, preco_unitario, ...} ],
            "taxa_liquidacao": float,
            "emolumentos": float,
            "liquido": float,
            "texto_bruto": str,
            "erro": str | None
        }
    """
    resultado = {
        "numero_nota": "N/A",
        "data_pregao": "",
        "corretora": "",
        "parser_usado": "",
        "operacoes": [],
        "taxa_liquidacao": 0.0,
        "emolumentos": 0.0,
        "liquido": 0.0,
        "texto_bruto": "",
        "erro": None,
    }

    try:
        reader = PdfReader(caminho_pdf)
        texto = "\n".join(page.extract_text() or "" for page in reader.pages)
        resultado["texto_bruto"] = texto
    except Exception as e:
        resultado["erro"] = f"Erro ao ler PDF: {e}"
        return resultado

    if not texto.strip():
        resultado["erro"] = "O PDF não contém texto extraível (pode ser imagem escaneada)."
        return resultado

    parser = get_parser_nota(texto)
    resultado["parser_usado"] = parser.NOME

    try:
        dados = parser.parsear(texto)
        resultado.update(dados)
    except Exception as e:
        resultado["erro"] = f"Erro no parser {parser.NOME}: {e}"

    return resultado


def resumo_nota(dados_nota: dict) -> str:
    """Retorna um resumo textual da nota para exibir no app."""
    if dados_nota.get("erro"):
        return f"❌ Erro: {dados_nota['erro']}"

    linhas = [
        f"📄 Nota #{dados_nota['numero_nota']}",
        f"📅 Data: {dados_nota['data_pregao']}",
        f"🏦 Corretora: {dados_nota['corretora']}",
        f"🔍 Parser: {dados_nota.get('parser_usado', '?')}",
        f"📊 Operações encontradas: {len(dados_nota['operacoes'])}",
        "",
    ]
    for op in dados_nota["operacoes"]:
        emoji = "🟢" if op["tipo"] == "COMPRA" else "🔴"
        linhas.append(
            f"  {emoji} {op['tipo']} {op['quantidade']}x {op['ticker']} "
            f"@ R$ {op['preco_unitario']:.2f} = R$ {op['valor_total']:.2f}"
        )
    linhas += [
        "",
        f"💸 Taxa liquidação: R$ {dados_nota['taxa_liquidacao']:.2f}",
        f"💸 Emolumentos: R$ {dados_nota['emolumentos']:.2f}",
        f"💰 Líquido: R$ {dados_nota['liquido']:.2f}",
    ]
    return "\n".join(linhas)
