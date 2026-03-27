"""
Parser genérico de Nota de Negociação — fallback para corretoras não identificadas.

Detectado por: sempre retorna True (usado como último recurso).
Suporta: qualquer nota no formato BOVESPA padrão + fallback linha-a-linha.
"""

import re
from .base import NotaParser, limpar_valor, determinar_tipo_ativo
from .nubank_nota import parse_bovespa_padrao, _extrair_numero_nota, _extrair_data


_CORRETORAS = {
    "nu invest": "Nu Investimentos",
    "nuinvest": "Nu Investimentos",
    "xp investimentos": "XP",
    "clear": "Clear",
    "rico": "Rico",
    "btg": "BTG Pactual",
    "itaú": "Itaú",
    "bradesco": "Bradesco",
    "inter": "Inter",
    "ágora": "Ágora",
    "modal": "Modal",
    "genial": "Genial",
}


def _detectar_corretora(texto: str) -> str:
    tl = texto.lower()
    for chave, nome in _CORRETORAS.items():
        if chave in tl:
            return nome
    return "Desconhecida"


class GenericoNotaParser(NotaParser):
    NOME = "Genérico (fallback)"
    PRIORIDADE = 100  # sempre o último

    @classmethod
    def detectar(cls, texto: str) -> bool:
        return True  # aceita qualquer texto

    @classmethod
    def parsear(cls, texto: str) -> dict:
        corretora = _detectar_corretora(texto)
        resultado = parse_bovespa_padrao(texto, corretora=corretora)

        # Se o parser BOVESPA padrão não encontrou nada, tenta fallback linha-a-linha
        if not resultado["operacoes"]:
            resultado["operacoes"] = _fallback_linhas(texto)

        return resultado


def _fallback_linhas(texto: str) -> list:
    """
    Fallback: busca padrões ticker + C/V + qtd + preço em cada linha.
    Útil para formatos que não seguem exatamente o padrão BOVESPA.
    """
    operacoes = []
    padrao = re.compile(
        r"([A-Z]{4}\d{1,3}[A-Z]?)\s+.*?([CV])\s+.*?(\d[\d.]*)\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})"
    )
    for linha in texto.split("\n"):
        if len(linha) < 20:
            continue
        m = padrao.search(linha)
        if m:
            ticker, cv, qtd_str, preco_str, valor_str = m.groups()
            operacoes.append({
                "ticker": ticker,
                "tipo": "COMPRA" if cv == "C" else "VENDA",
                "tipo_mercado": "VISTA",
                "especificacao": "",
                "quantidade": int(limpar_valor(qtd_str.replace(".", ""))),
                "preco_unitario": limpar_valor(preco_str),
                "valor_total": limpar_valor(valor_str),
                "taxa_rateio": 0.0,
                "tipo_ativo": determinar_tipo_ativo(ticker),
            })
    return operacoes
