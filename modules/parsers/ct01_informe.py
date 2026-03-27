"""
Parser de Informe de Rendimentos — CT01 (Comprovante de Rendimentos Pagos)
Receita Federal do Brasil — IN RFB nº 1.522/2014 e posteriores.

Detectado por: "Comprovante de Rendimentos Pagos" no texto base do PDF.

Particularidade: os valores são preenchidos como anotações FreeText
(tipo Typewriter) pelo usuário via leitor de PDF (ex: Preview, PDF Expert).
O content stream do PDF contém apenas o template em branco; os dados ficam
nas 37 anotações /Annots da página.

Layout CT01 — mapeamento por faixa de y-coordenada (origem inferior-esquerda):

  y ≈ 750+   → Exercício (ano)
  y ≈ 660-680 → Seção 1: CNPJ e Nome da fonte pagadora
  y ≈ 610-650 → Seção 2: CPF, Nome, Natureza do beneficiário
  y ≈ 525-595 → Seção 3: 5 campos tributáveis  (linhas 3.1 a 3.5)
  y ≈ 395-510 → Seção 4: 7 campos isentos       (linhas 4.1 a 4.7)
  y ≈ 338-380 → Seção 5: 3 campos exclusivos     (linhas 5.1 a 5.3)
  y ≈ 225-290 → Seção 6: 5 campos acumulados     (linhas 6.1 a 6.5)
  y ≈ 35-55   → Seção 8: Assinatura e data
"""

import re
from .base import InformeParser, limpar_valor

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader


# ─── Rótulos dos campos por seção (ordem top→bottom = y decrescente) ──────────

_SEC3_LABELS = [
    "Total dos rendimentos (inclusive férias)",
    "Contribuição previdenciária oficial",
    "Contribuições a entidades de previdência complementar (FAPI)",
    "Pensão alimentícia",
    "Imposto sobre a renda retido na fonte (seção 3)",
]

_SEC4_LABELS = [
    "Parcela isenta de aposentadoria (65 anos ou mais)",
    "Diárias e ajudas de custo",
    "Pensão/aposentadoria por moléstia grave",
    "Lucros e dividendos (desde 1996)",
    "Valores pagos ao sócio/titular de ME/EPP",
    "Indenizações por rescisão contratual (PDV)",
    "Outros isentos (especificar)",
]

_SEC5_LABELS = [
    "Décimo terceiro salário",
    "IRRF sobre 13º salário",
    "Outros (tributação exclusiva)",
]

_SEC6_LABELS = [
    "Total dos rendimentos tributáveis (acumulado)",
    "Exclusão: despesas com ação judicial",
    "Dedução: contribuição previdenciária oficial",
    "Dedução: pensão alimentícia",
    "IRRF (acumulado)",
]


class CT01InformeParser(InformeParser):
    NOME = "CT01 — Comprovante de Rendimentos (Receita Federal)"
    PRIORIDADE = 15  # após Nubank, antes do genérico

    @classmethod
    def detectar(cls, texto: str) -> bool:
        return bool(re.search(
            r"Comprovante de Rendimentos Pagos|CT01\s*-\s*\d{2}/\d{4}",
            texto, re.IGNORECASE
        ))

    @classmethod
    def parsear(cls, texto: str, ano_ant: str, ano_base: str) -> dict:
        # ano_base é passado pelo chamador, mas para CT01 extraímos do campo exercício
        return {
            "fontes_pagadoras": [],      # preenchido em ler_informe_ct01()
            "rendimentos_tributaveis": [],
            "rendimentos_isentos": [],
            "bens_direitos": [],
            "criptomoedas": [],
            "_ct01": True,               # sinaliza que precisa de leitura de anotações
        }


# ─── Leitura das anotações (chamada diretamente pelo informe_rendimentos.py) ──

def ler_informe_ct01(caminho_pdf: str) -> dict:
    """
    Lê o CT01 extraindo dados das anotações FreeText.
    Retorna o mesmo dict de ler_informe_rendimentos().
    """
    resultado = {
        "titular": None,
        "cpf": None,
        "ano_calendario": None,
        "parser_usado": CT01InformeParser.NOME,
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
        page = reader.pages[0]
        resultado["texto_bruto"] = page.extract_text() or ""
    except Exception as e:
        resultado["erro"] = f"Erro ao ler PDF: {e}"
        return resultado

    # Lê todas as anotações
    annots_raw = page.get('/Annots')
    if annots_raw is None:
        resultado["erro"] = "CT01 sem anotações — o formulário está em branco."
        return resultado

    annots_raw = annots_raw.get_object()
    anotacoes = []
    for a in annots_raw:
        if hasattr(a, 'get_object'):
            a = a.get_object()
        conteudo = str(a.get('/Contents', '')).strip()
        rect = a.get('/Rect')
        if rect is None:
            continue
        if hasattr(rect, '__iter__'):
            coords = [float(x) for x in rect]
        else:
            continue
        y_bottom = coords[1]   # coordenada y inferior (PDF: origem canto inf-esq)
        anotacoes.append({"conteudo": conteudo, "y": y_bottom, "x": coords[0]})

    # Ordena top→bottom (y decrescente no sistema PDF)
    anotacoes.sort(key=lambda a: -a["y"])

    # ── Extrai campos por faixa de y ──────────────────────────────────────────

    def _na_faixa(a, y_min, y_max):
        return y_min <= a["y"] <= y_max

    def _valor_faixa(y_min, y_max) -> list[str]:
        return [a["conteudo"] for a in anotacoes if _na_faixa(a, y_min, y_max) and a["conteudo"]]

    # Exercício / ano-calendário
    exercicio_vals = _valor_faixa(740, 780)
    if exercicio_vals:
        try:
            exercicio = int(re.search(r"\d{4}", exercicio_vals[0]).group())
            resultado["ano_calendario"] = exercicio - 1  # exercício 2026 = ano-cal 2025
        except Exception:
            pass

    # Seção 1: Fonte Pagadora
    sec1_vals = sorted([a for a in anotacoes if 655 <= a["y"] <= 685], key=lambda a: a["x"])
    cnpj_fp = sec1_vals[0]["conteudo"] if len(sec1_vals) > 0 else ""
    nome_fp  = sec1_vals[1]["conteudo"] if len(sec1_vals) > 1 else ""
    if nome_fp or cnpj_fp:
        resultado["fontes_pagadoras"].append({"nome": nome_fp, "cnpj": cnpj_fp})

    # Seção 2: Beneficiário
    sec2_vals = sorted([a for a in anotacoes if 600 <= a["y"] <= 650], key=lambda a: -a["y"])
    for a in sec2_vals:
        c = a["conteudo"]
        if re.match(r"\d{3}[\.\*]{1}", c):
            resultado["cpf"] = c
        elif c and not resultado["titular"]:
            resultado["titular"] = c

    # Seção 3: Rendimentos Tributáveis
    sec3 = sorted([a for a in anotacoes if 520 <= a["y"] <= 600], key=lambda a: -a["y"])
    for i, a in enumerate(sec3):
        rotulo = _SEC3_LABELS[i] if i < len(_SEC3_LABELS) else f"Campo 3.{i+1}"
        valor = limpar_valor(a["conteudo"])
        resultado["rendimentos_tributaveis"].append({
            "codigo": f"3.{i+1}",
            "tipo": "Rendimento do Trabalho (CT01)",
            "especificacao": rotulo,
            "valor": valor,
            "categoria": "TRIBUTAVEL",
        })

    # Seção 4: Rendimentos Isentos
    sec4 = sorted([a for a in anotacoes if 390 <= a["y"] <= 515], key=lambda a: -a["y"])
    for i, a in enumerate(sec4):
        rotulo = _SEC4_LABELS[i] if i < len(_SEC4_LABELS) else f"Campo 4.{i+1}"
        valor = limpar_valor(a["conteudo"])
        if valor > 0:
            resultado["rendimentos_isentos"].append({
                "codigo": f"4.{i+1}",
                "tipo": "Rendimento Isento (CT01)",
                "especificacao": rotulo,
                "valor": valor,
                "categoria": "ISENTO",
            })

    # Seção 5: Rendimentos com Tributação Exclusiva
    sec5 = sorted([a for a in anotacoes if 335 <= a["y"] <= 385], key=lambda a: -a["y"])
    for i, a in enumerate(sec5):
        rotulo = _SEC5_LABELS[i] if i < len(_SEC5_LABELS) else f"Campo 5.{i+1}"
        valor = limpar_valor(a["conteudo"])
        if valor > 0:
            resultado["rendimentos_tributaveis"].append({
                "codigo": f"5.{i+1}",
                "tipo": "Tributação Exclusiva (CT01)",
                "especificacao": rotulo,
                "valor": valor,
                "categoria": "TRIBUTAVEL_EXCLUSIVO",
            })

    resultado["total_tributavel"] = sum(
        r["valor"] for r in resultado["rendimentos_tributaveis"]
    )
    resultado["total_isento"] = sum(
        r["valor"] for r in resultado["rendimentos_isentos"]
    )

    return resultado
