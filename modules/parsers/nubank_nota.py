"""
Parser de Nota de Negociação — Nu Invest / NuInvest

Detectado por: presença de "Nu Invest" ou "nuinvest" no texto.
Formato: BOVESPA padrão com mercados VISTA / FRACIONARIO / TERMO.
"""

import re
from datetime import datetime
from .base import NotaParser, limpar_valor, determinar_tipo_ativo


class NubankNotaParser(NotaParser):
    NOME = "Nu Invest"
    PRIORIDADE = 10

    @classmethod
    def detectar(cls, texto: str) -> bool:
        return bool(re.search(r"nu\s*invest|nuinvest", texto, re.IGNORECASE))

    @classmethod
    def parsear(cls, texto: str) -> dict:
        return _parse_bovespa_padrao(texto, corretora="Nu Investimentos")


# ─── Lógica BOVESPA padrão (reutilizável por outras corretoras) ───────────────

_PADRAO_OP = re.compile(
    r"BOVESPA\s+([CV])\s+(VISTA|FRACIONARIO|TERMO|OPC[AÃ]O)\s+"
    r"([A-Z]{4}\d{1,3}[A-Z]?)\s+"
    r"(.*?)\s*@?\s*"
    r"(\d[\d.]*)\s+"
    r"([\d.]+,\d{2})\s+"
    r"([\d.]+,\d{2})\s*"
    r"([DC])",
)


def _extrair_numero_nota(texto: str) -> str:
    match = re.search(r"[Nn][úu]mero\s+da\s+nota\s*\n?\s*(\d+)", texto)
    if match:
        return match.group(1)
    match = re.search(r"nota[:\s]+(\d{5,})", texto, re.IGNORECASE)
    return match.group(1) if match else "N/A"


def _extrair_data(texto: str) -> str:
    match = re.search(r"[Dd]ata\s+[Pp]reg[aã]o\s*\n?\s*(\d{2}/\d{2}/\d{4})", texto)
    if match:
        d, m, a = match.group(1).split("/")
        return f"{a}-{m}-{d}"
    match = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    if match:
        d, m, a = match.group(1).split("/")
        return f"{a}-{m}-{d}"
    return datetime.today().strftime("%Y-%m-%d")


def _parse_bovespa_padrao(texto: str, corretora: str) -> dict:
    resultado = {
        "corretora": corretora,
        "numero_nota": _extrair_numero_nota(texto),
        "data_pregao": _extrair_data(texto),
        "operacoes": [],
        "taxa_liquidacao": 0.0,
        "emolumentos": 0.0,
        "liquido": 0.0,
    }

    # Taxas
    m = re.search(r"Taxa de Liquidaç[aã]o[^\d-]*(-?[\d.]+,\d{2})", texto)
    if m:
        resultado["taxa_liquidacao"] = abs(limpar_valor(m.group(1)))

    m = re.search(r"Emolumentos[^\d-]*(-?[\d.]+,\d{2})", texto)
    if m:
        resultado["emolumentos"] = abs(limpar_valor(m.group(1)))

    m = re.search(r"[Ll][íi]quido para.*?(\d{1,3}(?:\.\d{3})*,\d{2})", texto, re.DOTALL)
    if m:
        resultado["liquido"] = limpar_valor(m.group(1))

    # Operações
    operacoes_raw = []
    vistos = set()
    for pos in re.finditer(r"BOVESPA", texto):
        chunk = " ".join(texto[pos.start(): pos.start() + 350].split())
        match = _PADRAO_OP.search(chunk)
        if match:
            chave = (match.group(3), match.group(5), match.group(6))
            if chave not in vistos:
                vistos.add(chave)
                operacoes_raw.append(match.groups())

    total_valor = sum(limpar_valor(op[6]) for op in operacoes_raw)
    taxa_total = resultado["taxa_liquidacao"] + resultado["emolumentos"]

    for op in operacoes_raw:
        cv, mercado, ticker, espec, qtd_str, preco_str, valor_str, dc = op
        quantidade = limpar_valor(qtd_str.replace(".", ""))
        quantidade = int(quantidade) if quantidade == int(quantidade) else quantidade
        preco = limpar_valor(preco_str)
        valor = limpar_valor(valor_str)
        taxa_rateio = (valor / total_valor * taxa_total) if total_valor > 0 else 0.0

        # Normaliza fracionário: KLBN4F → KLBN4
        ticker_norm = re.sub(r"F$", "", ticker) if mercado == "FRACIONARIO" else ticker

        resultado["operacoes"].append({
            "ticker": ticker_norm,
            "tipo": "COMPRA" if cv == "C" else "VENDA",
            "tipo_mercado": mercado,
            "especificacao": espec.strip(),
            "quantidade": quantidade,
            "preco_unitario": preco,
            "valor_total": valor,
            "taxa_rateio": round(taxa_rateio, 4),
            "tipo_ativo": determinar_tipo_ativo(ticker_norm),
        })

    return resultado


# Exporta para reutilização por outros parsers com mesmo formato
parse_bovespa_padrao = _parse_bovespa_padrao
