"""
Parser genérico de Informe de Rendimentos — fallback para corretoras não identificadas.

Detectado por: sempre retorna True.
Espera seções em MAIÚSCULAS: RENDIMENTOS SUJEITOS A TRIBUTAÇÃO EXCLUSIVA,
RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS, BENS E DIREITOS, CRIPTOMOEDAS.
"""

import re
from .base import InformeParser, limpar_valor, extrair_cnpj


class GenericoInformeParser(InformeParser):
    NOME = "Genérico (fallback)"
    PRIORIDADE = 100

    @classmethod
    def detectar(cls, texto: str) -> bool:
        return True

    @classmethod
    def parsear(cls, texto: str, ano_ant: str, ano_base: str) -> dict:
        return {
            "fontes_pagadoras":        _extrair_fontes(texto),
            "rendimentos_tributaveis": _extrair_tributaveis(texto),
            "rendimentos_isentos":     _extrair_isentos(texto),
            "bens_direitos":           _extrair_bens(texto, ano_ant, ano_base),
            "criptomoedas":            _extrair_criptos(texto),
        }


# ─── Extratores ───────────────────────────────────────────────────────────────

def _extrair_fontes(texto: str) -> list:
    fontes = []
    vistos = set()
    padrao = re.compile(
        r"([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇÀÜÑ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇÀÜÑ\s\-,\.]+?)\s+"
        r"CNPJ[:\s]+(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})",
        re.MULTILINE
    )
    for m in padrao.finditer(texto):
        nome = m.group(1).strip()
        cnpj = m.group(2).strip()
        if len(nome) > 5 and cnpj not in vistos:
            vistos.add(cnpj)
            fontes.append({"nome": nome, "cnpj": cnpj})
    return fontes


def _extrair_tributaveis(texto: str) -> list:
    rendimentos = []
    sec = re.search(
        r"RENDIMENTOS SUJEITOS A TRIBUTA[CÇ][AÃ]O EXCLUSIVA(.+?)"
        r"(?:RENDIMENTOS ISENTOS|BENS E DIREITOS|CRIPTOMOEDAS|$)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if not sec:
        return rendimentos
    padrao = re.compile(
        r"(\d+)\.\s+([^\n\r]{5,60}?)\s{2,}([^\n\r]{3,50}?)\s{2,}(R\$\s*[\d.,]+)",
        re.MULTILINE
    )
    for m in padrao.finditer(sec.group(1)):
        valor = limpar_valor(m.group(4))
        if valor > 0:
            rendimentos.append({
                "codigo": m.group(1),
                "tipo": m.group(2).strip(),
                "especificacao": m.group(3).strip(),
                "valor": valor,
                "categoria": "TRIBUTAVEL_EXCLUSIVO",
            })
    return rendimentos


def _extrair_isentos(texto: str) -> list:
    rendimentos = []
    sec = re.search(
        r"RENDIMENTOS ISENTOS E N[AÃ]O TRIBUT[AÁ]VEIS(.+?)"
        r"(?:BENS E DIREITOS|CRIPTOMOEDAS|RENDIMENTOS SUJEITOS|$)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if not sec:
        return rendimentos
    secao = sec.group(1)
    padrao = re.compile(
        r"(\d+)\.\s+([^\n\r]{5,120}?)\s{2,}([^\n\r]{3,60}?)\s{2,}(R\$\s*[\d.,]+)",
        re.MULTILINE
    )
    for m in padrao.finditer(secao):
        valor = limpar_valor(m.group(4))
        if valor > 0 and "total" not in m.group(3).lower():
            rendimentos.append({
                "codigo": m.group(1),
                "tipo": m.group(2).strip()[:80],
                "especificacao": m.group(3).strip(),
                "valor": valor,
                "categoria": "ISENTO",
            })
    # Fallback LCI/LCA
    if not rendimentos:
        for m in re.finditer(r"(LCI|LCA|CRI|CRA|[Pp]oupan[çc]a)[^\n]*(R\$\s*[\d.,]+)", secao):
            valor = limpar_valor(m.group(2))
            if valor > 0:
                rendimentos.append({
                    "codigo": "12",
                    "tipo": "Rendimentos de LCI/LCA/CRI/CRA",
                    "especificacao": m.group(1),
                    "valor": valor,
                    "categoria": "ISENTO",
                })
    return rendimentos


def _extrair_bens(texto: str, ano_ant: str, ano_base: str) -> list:
    bens = []
    sec = re.search(
        r"BENS E DIREITOS(.+?)"
        r"(?:CRIPTOMOEDAS|RENDIMENTOS SUJEITOS|INFORMAÇÕES COMPLEMENTARES|$)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if not sec:
        return bens
    secao = sec.group(1)
    pares = re.findall(
        r"([A-Za-zÀ-ú][^\n\r]{5,50}?)\s+(R\$\s*[\d.,]+)\s+(R\$\s*[\d.,]+)",
        secao
    )
    for descricao, v1, v2 in pares:
        if "total" in descricao.lower():
            continue
        bens.append({
            "grupo": "—",
            "codigo_tipo": "—",
            "especificacao": descricao.strip()[:60],
            "cnpj": extrair_cnpj(descricao),
            "ano_anterior": ano_ant,
            "ano_base": ano_base,
            "saldo_anterior": limpar_valor(v1),
            "saldo_base": limpar_valor(v2),
        })
    return bens


def _extrair_criptos(texto: str) -> list:
    criptos = []
    sec = re.search(
        r"CRIPTOMOEDAS(.+?)(?:INFORMAÇÕES COMPLEMENTARES|$)",
        texto, re.DOTALL | re.IGNORECASE
    )
    if not sec:
        return criptos
    padrao = re.compile(
        r"([A-Za-zÀ-ú][A-Za-zÀ-ú\s]+?)\s+-\s+([A-Z]{2,10})\s+"
        r"(\d{2}/\d{2}/\d{4})\s+"
        r"([\d,]+(?:\.\d+)?)\s+[A-Z]+\s+"
        r"(R\$\s*[\d.,]+)\s+"
        r"(R\$\s*[\d.,]+)",
        re.MULTILINE
    )
    for m in padrao.finditer(sec.group(1)):
        try:
            quantidade = float(m.group(4).replace(".", "").replace(",", "."))
        except ValueError:
            quantidade = 0.0
        criptos.append({
            "nome": m.group(1).strip(),
            "ticker": m.group(2).strip(),
            "data": m.group(3).strip(),
            "quantidade": quantidade,
            "saldo_reais": limpar_valor(m.group(5)),
            "custo_medio_aquisicao": limpar_valor(m.group(6)),
        })
    return criptos
