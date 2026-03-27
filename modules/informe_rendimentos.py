"""
Módulo para leitura e extração de dados de Informes de Rendimentos Financeiros.

Delega para o sistema de parsers em modules/parsers/.
Para adicionar suporte a uma nova corretora, veja modules/parsers/__init__.py.

Seções extraídas:
  - Identificação da fonte pagadora (nome + CNPJ)
  - Rendimentos sujeitos à tributação exclusiva
  - Rendimentos isentos e não tributáveis
  - Bens e Direitos (saldo 31/12/ano anterior e 31/12/ano base)
  - Criptomoedas

Dependências: pypdf
"""

import re
from .parsers import get_parser_informe, listar_parsers_informe
from .parsers.ct01_informe import CT01InformeParser, ler_informe_ct01

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader


def _extrair_cpf(texto: str) -> str | None:
    match = re.search(r"\d{3}\.\*\*\*\.\*\*\*-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", texto)
    return match.group(0) if match else None


def _extrair_ano(texto: str) -> int | None:
    match = re.search(r"[Aa]no[- ][Cc]alend[aá]rio\s+(?:de\s+)?(\d{4})", texto)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{4})", texto[:300])
    return int(match.group(1)) if match else None


def ler_informe_rendimentos(caminho_pdf: str) -> dict:
    """
    Lê um informe de rendimentos em PDF e extrai os dados.

    Retorna:
        {
            "titular": str | None,
            "cpf": str | None,
            "ano_calendario": int | None,
            "parser_usado": str,
            "fontes_pagadoras": [ {nome, cnpj} ],
            "rendimentos_tributaveis": [ {codigo, tipo, especificacao, valor, categoria} ],
            "rendimentos_isentos": [ {codigo, tipo, especificacao, valor, categoria} ],
            "bens_direitos": [ {grupo, codigo_tipo, especificacao, saldo_anterior, saldo_base} ],
            "criptomoedas": [ ... ],
            "total_tributavel": float,
            "total_isento": float,
            "texto_bruto": str,
            "erro": str | None
        }
    """
    resultado = {
        "titular": None,
        "cpf": None,
        "ano_calendario": None,
        "parser_usado": "",
        "fontes_pagadoras": [],
        "rendimentos_tributaveis": [],
        "rendimentos_isentos": [],
        "bens_direitos": [],
        "criptomoedas": [],
        "total_tributavel": 0.0,
        "total_isento": 0.0,
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

    # Titular e CPF
    cpf = _extrair_cpf(texto)
    resultado["cpf"] = cpf
    if cpf:
        idx = texto.find(cpf)
        trecho = texto[max(0, idx - 300):idx]
        for linha in reversed([l.strip() for l in trecho.split("\n") if l.strip()]):
            if re.match(r"^[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇa-záéíóúâêîôûãõç\s]{5,}$", linha):
                resultado["titular"] = linha
                break

    resultado["ano_calendario"] = _extrair_ano(texto)

    # Anos para passar ao parser
    anos = re.findall(r"31/12/(\d{4})", texto)
    ano_ant  = anos[0] if len(anos) >= 1 else str((resultado["ano_calendario"] or 2025) - 1)
    ano_base = anos[1] if len(anos) >= 2 else str(resultado["ano_calendario"] or 2025)

    parser = get_parser_informe(texto)
    resultado["parser_usado"] = parser.NOME

    # CT01 requer leitura das anotações — não pode ser feito pelo parsear() genérico
    if parser is CT01InformeParser:
        return ler_informe_ct01(caminho_pdf)

    try:
        dados = parser.parsear(texto, ano_ant=ano_ant, ano_base=ano_base)
        resultado.update(dados)
    except Exception as e:
        resultado["erro"] = f"Erro no parser {parser.NOME}: {e}"

    resultado["total_tributavel"] = sum(r["valor"] for r in resultado["rendimentos_tributaveis"])
    resultado["total_isento"]     = sum(r["valor"] for r in resultado["rendimentos_isentos"])

    return resultado
