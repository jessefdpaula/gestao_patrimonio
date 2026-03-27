"""
Parser de Informe de Rendimentos — Nubank / Nu Invest / Nu Financeira

Detectado por: presença de "nubank", "nu investimentos" ou "nu financeira".

Formato Nubank:
  - Bens e Direitos por "Grupo NN - descrição" / "Código NN - descrição"
  - Grupo 03: ações (quantidade, não valor monetário)
  - Grupo 04: renda fixa (2 ou 3 colunas R$; 3ª = rendimento tributável para Código 02)
  - Grupo 06: conta corrente
  - Grupo 07: FIIs / FIAgros (cotas, não valor monetário)
  - Grupo 99: outros (dividendos creditados, etc.)
  - Rendimentos isentos por "Tipo de rendimento(s) NN - descrição"
  - Fontes pagadoras por "Fonte pagadora: nome"
"""

import re
from .base import InformeParser, limpar_valor


_LINHAS_IGNORAR = {
    "título", "vencimento", "agência", "conta", "rendimento isento",
    "rendimento tributação exclusiva", "código de negociação",
    "quantidade em 2024", "quantidade em 2025", "cotas em 2024", "cotas em 2025",
    "ativo", "valor total", "31/12/2024", "31/12/2025",
    "valor", "c/v", "tipo de mercado",
}

_KW_IGNORAR = [
    "grupo", "código", "localização", "cnpj:", "fonte pagadora",
    "discriminação sugerida", "dúvidas frequentes", "por que o",
    "qual a diferença", "como declarar", "entenda", "saiba mais",
    "passo-a-passo", "clique no", "declare cada", "caso haja",
    "quais produtos", "o que são", "convers", "acesse", "para consultar",
    "você investe", "os valores dos proventos", "para declarar cada posição",
    "lembre-se", "informe o valor", "se não constam", "tem alguma",
]


def _deve_ignorar(linha: str) -> bool:
    l = linha.strip().lower()
    if not l:
        return True
    if l in _LINHAS_IGNORAR:
        return True
    if re.match(r"^\d{2}/\d{2}/\d{4}$", l):
        return True
    for kw in _KW_IGNORAR:
        if kw in l:
            return True
    return False


def _blocos_por_grupo(texto: str) -> list[tuple[str, str, str]]:
    """Divide texto em blocos por 'Grupo NN -'. Retorna (grupo_num, codigo_desc, bloco_texto)."""
    positions = [m.start() for m in re.finditer(r"Grupo \d{2}\s*-", texto)]
    resultado = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(texto)
        bloco = texto[pos:end]
        grupo_m = re.match(r"Grupo (\d{2})\s*-", bloco)
        grupo_num = grupo_m.group(1) if grupo_m else "00"
        resultado.append((grupo_num, bloco))
    return resultado


class NubankInformeParser(InformeParser):
    NOME = "Nubank / Nu Invest"
    PRIORIDADE = 10

    @classmethod
    def detectar(cls, texto: str) -> bool:
        return bool(re.search(r"nubank|nu investimentos|nu financeira", texto, re.IGNORECASE))

    @classmethod
    def parsear(cls, texto: str, ano_ant: str, ano_base: str) -> dict:
        bens, tributaveis = _parse_bens(texto, ano_ant, ano_base)
        return {
            "fontes_pagadoras": _parse_fontes(texto),
            "rendimentos_tributaveis": tributaveis,
            "rendimentos_isentos": _parse_isentos(texto),
            "bens_direitos": bens,
            "criptomoedas": [],
        }


# ─── Extratores internos ──────────────────────────────────────────────────────

def _parse_bens(texto: str, ano_ant: str, ano_base: str) -> tuple[list, list]:
    bens = []
    tributaveis = []

    for grupo_num, bloco in _blocos_por_grupo(texto):
        codigo_m = re.search(r"C[oó]digo (\d{2})\s*-\s*(.+?)(?:\n|$)", bloco)
        codigo_num  = codigo_m.group(1) if codigo_m else "00"
        codigo_desc = (codigo_m.group(2).strip()[:70] if codigo_m else "")

        cnpj_m = re.search(r"CNPJ:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", bloco)
        cnpj = cnpj_m.group(1) if cnpj_m else None

        def _bem(especificacao, saldo_ant=0.0, saldo_base_val=0.0):
            return {
                "grupo": grupo_num,
                "codigo_tipo": f"{codigo_num} - {codigo_desc}",
                "especificacao": especificacao,
                "cnpj": cnpj,
                "ano_anterior": ano_ant,
                "ano_base": ano_base,
                "saldo_anterior": saldo_ant,
                "saldo_base": saldo_base_val,
            }

        # ── Grupo 04: Renda Fixa ──────────────────────────────────────────────
        if grupo_num == "04":
            for m in re.finditer(
                r"^([^\n]+?)\s+(R\$\s*[\d.,]+)\s+(R\$\s*[\d.,]+)(?:\s+(R\$\s*[\d.,]+))?",
                bloco, re.MULTILINE
            ):
                desc = m.group(1).strip()
                if _deve_ignorar(desc):
                    continue
                sa = limpar_valor(m.group(2))
                sb = limpar_valor(m.group(3))
                rend = limpar_valor(m.group(4)) if m.group(4) else 0.0
                if sa == 0 and sb == 0 and rend == 0:
                    continue
                bens.append(_bem(desc[:70], sa, sb))
                if rend > 0 and codigo_num == "02":
                    tributaveis.append({
                        "codigo": "6",
                        "tipo": "Rendimento de aplicação financeira",
                        "especificacao": f"{codigo_desc} — {desc}",
                        "valor": rend,
                        "categoria": "TRIBUTAVEL_EXCLUSIVO",
                    })

        # ── Grupo 03: Ações (quantidade) ──────────────────────────────────────
        elif grupo_num == "03":
            for m in re.finditer(r"^([A-Z]{4}\d{1,2}[A-Z]?)\s+(\d+)\s+(\d+)", bloco, re.MULTILINE):
                bens.append(_bem(
                    f"{m.group(1)} — {m.group(2)} ações ({ano_ant}) / {m.group(3)} ações ({ano_base})"
                ))

        # ── Grupo 06: Conta corrente ──────────────────────────────────────────
        elif grupo_num == "06":
            for m in re.finditer(
                r"^([^\n]+?)\s+(R\$\s*[\d.,]+)\s+(R\$\s*[\d.,]+)",
                bloco, re.MULTILINE
            ):
                desc = m.group(1).strip()
                if _deve_ignorar(desc):
                    continue
                sa = limpar_valor(m.group(2))
                sb = limpar_valor(m.group(3))
                if sa == 0 and sb == 0:
                    continue
                bens.append(_bem(desc[:70], sa, sb))

        # ── Grupo 07: FIIs / FIAgros (cotas) ─────────────────────────────────
        elif grupo_num == "07":
            single = re.findall(r"^([A-Z]{4}11)\s+(\d+)\s+(\d+)", bloco, re.MULTILINE)
            if single:
                for ticker, q_ant, q_base in single:
                    bens.append(_bem(
                        f"{ticker} — {q_ant} cotas ({ano_ant}) / {q_base} cotas ({ano_base})"
                    ))
            else:
                tickers = re.findall(r"^([A-Z]{4}11)$", bloco, re.MULTILINE)
                qtds    = re.findall(r"^(\d+)$",         bloco, re.MULTILINE)
                n = len(tickers)
                if n > 0 and len(qtds) >= 2 * n:
                    for j, ticker in enumerate(tickers):
                        bens.append(_bem(
                            f"{ticker} — {qtds[j]} cotas ({ano_ant}) / {qtds[n + j]} cotas ({ano_base})"
                        ))

        # ── Grupo 99: Outros (dividendos creditados, etc.) ────────────────────
        elif grupo_num == "99":
            for m in re.finditer(
                r"^([A-Z]{4}\d{1,2}[A-Z]?)\s+(R\$\s*[\d.,]+)\s+(R\$\s*[\d.,]+)",
                bloco, re.MULTILINE
            ):
                bens.append(_bem(m.group(1), limpar_valor(m.group(2)), limpar_valor(m.group(3))))

    return bens, tributaveis


def _parse_isentos(texto: str) -> list:
    isentos = []
    sec_m = re.search(r"Rendimentos isentos e n[ãa]o tribut[áa]veis", texto, re.IGNORECASE)
    if not sec_m:
        return isentos

    secao = texto[sec_m.start():]
    stop_m = re.search(r"D[íi]vidas e [ôo]nus|\Z", secao, re.IGNORECASE)
    if stop_m:
        secao = secao[:stop_m.start()]

    tipo_matches = list(re.finditer(r"Tipo de rendimento[s]?\s+(\d+)\s*[-–]\s*([^\n]+)", secao))

    for i, tipo_m in enumerate(tipo_matches):
        codigo    = tipo_m.group(1)
        tipo_desc = tipo_m.group(2).strip()
        bloco_start = tipo_m.end()
        bloco_end   = tipo_matches[i + 1].start() if i + 1 < len(tipo_matches) else len(secao)
        bloco = secao[bloco_start:bloco_end]

        same = re.findall(r"([A-Z]{4}\d{1,2}[A-Z]?)\s+(R\$\s*[\d.,]+)", bloco)
        if same:
            for ticker, valor_str in same:
                valor = limpar_valor(valor_str)
                if valor > 0:
                    isentos.append({
                        "codigo": codigo,
                        "tipo": tipo_desc[:80],
                        "especificacao": ticker,
                        "valor": valor,
                        "categoria": "ISENTO",
                    })
        else:
            tickers = re.findall(r"^([A-Z]{4}\d{1,2}[A-Z]?)$", bloco, re.MULTILINE)
            valores  = re.findall(r"R\$\s*([\d.,]+)", bloco)
            for j, ticker in enumerate(tickers):
                if j < len(valores):
                    valor = limpar_valor(valores[j])
                    if valor > 0:
                        isentos.append({
                            "codigo": codigo,
                            "tipo": tipo_desc[:80],
                            "especificacao": ticker,
                            "valor": valor,
                            "categoria": "ISENTO",
                        })
    return isentos


def _parse_fontes(texto: str) -> list:
    fontes = []
    vistos = set()
    for m in re.finditer(r"Fonte pagadora:\s*([^\n]+)", texto):
        nome = m.group(1).strip()
        trecho = texto[max(0, m.start() - 300):m.start() + 200]
        cnpj_m = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", trecho)
        cnpj = cnpj_m.group(1) if cnpj_m else ""
        chave = cnpj or nome
        if chave not in vistos:
            vistos.add(chave)
            fontes.append({"nome": nome, "cnpj": cnpj})

    if not fontes:
        for m in re.finditer(
            r"([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇÀÜÑ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇÀÜÑ\s\-,\.]+?)\s+CNPJ[:\s]+(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})",
            texto
        ):
            nome = m.group(1).strip()
            cnpj = m.group(2)
            if len(nome) > 5 and cnpj not in vistos:
                vistos.add(cnpj)
                fontes.append({"nome": nome, "cnpj": cnpj})

    return fontes
