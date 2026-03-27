"""
Parser de Informe de Rendimentos — Bradesco / Ágora.

Detectado por: "Informe de rendimentos financeiros" + "BANCO BRADESCO"
Suporta PDFs multi-instituição (Bradesco Banco + Ágora + Bradesco Capitalização).

Estrutura do PDF:
  Página 1: Bradesco Banco — Poupança (seção 3), CDB (seção 4), Conta Corrente (seção 5)
  Página 3: Ágora — geralmente tudo zerado
  Página 9: Bradesco Capitalização — Título de Capitalização (seção 2)

Formato dos dados:
  X.X.X.   DESCRICAO
  AGENCIA   CONTA   SALDO EM 31/12/YYYY   SALDO EM 31/12/YYYY   RENDIMENTO
  5750      440.072-0   10.046,50   7.510,43   940,85
  TOTAL X.X.X.   10.046,50   7.510,43   940,85
"""

import re
from .base import InformeParser, limpar_valor


def _tres_valores(texto: str) -> tuple[float, float, float]:
    """Extrai 3 valores monetários (ant, base, rend) de uma linha TOTAL."""
    vals = re.findall(r"[\d.]+,\d{2}", texto)
    vals = [limpar_valor(v) for v in vals]
    while len(vals) < 3:
        vals.append(0.0)
    return vals[0], vals[1], vals[2]


def _dois_valores(texto: str) -> tuple[float, float]:
    """Extrai 2 valores monetários (ant, base) de uma linha TOTAL."""
    vals = re.findall(r"[\d.]+,\d{2}", texto)
    vals = [limpar_valor(v) for v in vals]
    while len(vals) < 2:
        vals.append(0.0)
    return vals[0], vals[1]


class BradescoInformeParser(InformeParser):
    NOME = "Bradesco / Ágora — Informe de Rendimentos Financeiros"
    PRIORIDADE = 12

    @classmethod
    def detectar(cls, texto: str) -> bool:
        return bool(re.search(
            r"Informe de rendimentos financeiros",
            texto, re.IGNORECASE
        )) and bool(re.search(r"BANCO BRADESCO|Bradesco", texto, re.IGNORECASE))

    @classmethod
    def parsear(cls, texto: str, ano_ant: str, ano_base: str) -> dict:
        resultado = {
            "fontes_pagadoras": [],
            "rendimentos_tributaveis": [],
            "rendimentos_isentos": [],
            "bens_direitos": [],
            "criptomoedas": [],
        }

        # ── Fonte Pagadora ────────────────────────────────────────────────────
        # CNPJ vem como "60.746.948 Filial: 0001 Controle: 12" — monta manualmente
        m = re.search(
            r"Empresa:\s*(.+?)\s+CNPJ:\s*([\d.]+)\s+Filial:\s*(\d+)\s+Controle:\s*(\d+)",
            texto
        )
        if m:
            nome_fp = m.group(1).strip()
            base    = re.sub(r"\D", "", m.group(2))   # "60746948"
            filial  = m.group(3).zfill(4)              # "0001"
            ctrl    = m.group(4).zfill(2)              # "12"
            cnpj_fp = f"{base[:2]}.{base[2:5]}.{base[5:8]}/{filial}-{ctrl}"
            resultado["fontes_pagadoras"].append({"nome": nome_fp, "cnpj": cnpj_fp})
        else:
            nome_fp, cnpj_fp = "Bradesco", ""

        # ── Seção 3 — Rendimentos Isentos (Poupança, etc.) ───────────────────
        # Busca linhas TOTAL X.X.X. com 3 valores dentro da seção 3
        sec3_match = re.search(
            r"RENDIMENTOS ISENTOS(.+?)(?=\n\s*4\.|RENDIMENTOS SUJEITOS|$)",
            texto, re.DOTALL | re.IGNORECASE
        )
        if sec3_match:
            sec3 = sec3_match.group(1)

            # Poupança
            if re.search(r"POUPAN[CÇ]A|CADERNETA", sec3, re.IGNORECASE):
                m_tot = re.search(
                    r"TOTAL\s+3\.1\.1[.\s]+([\d.,\s]+)", sec3, re.IGNORECASE
                )
                if not m_tot:
                    m_tot = re.search(r"TOTAL\s+3\.1[.\s]+([\d.,\s]+)", sec3, re.IGNORECASE)
                if m_tot:
                    ant, base, rend = _tres_valores(m_tot.group(0))
                    if rend > 0:
                        resultado["rendimentos_isentos"].append({
                            "codigo": "12",
                            "especificacao": "Rendimentos de Caderneta de Poupança",
                            "valor": rend,
                            "fonte_nome": nome_fp,
                            "fonte_cnpj": cnpj_fp,
                        })
                    if ant > 0 or base > 0:
                        resultado["bens_direitos"].append({
                            "grupo": "06",
                            "codigo_tipo": "01",
                            "especificacao": f"Caderneta de Poupança — {nome_fp}",
                            "cnpj_instituicao": cnpj_fp,
                            "saldo_anterior": ant,
                            "saldo_base": base,
                        })

        # ── Seção 4 — Tributação Exclusiva (CDB, etc.) ───────────────────────
        sec4_match = re.search(
            r"RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA(.+?)"
            r"(?=TOTAL DOS RENDIMENTOS L[IÍ]QUIDOS|DEPOSITO BANCARIO|$)",
            texto, re.DOTALL | re.IGNORECASE
        )
        rend_exclusiva_match = re.search(
            r"TOTAL DOS RENDIMENTOS L[IÍ]QUIDOS SUJEITOS.*?([\d.]+,\d{2})",
            texto, re.IGNORECASE
        )

        if sec4_match:
            sec4 = sec4_match.group(0)

            # CDB
            if re.search(r"CDB|RENDA FIXA", sec4, re.IGNORECASE):
                m_tot = re.search(r"TOTAL\s+4\.\d+\.\d+[.\s]+([\d.,\s]+)", sec4)
                if m_tot:
                    ant, base, rend = _tres_valores(m_tot.group(0))
                    if ant > 0 or base > 0:
                        resultado["bens_direitos"].append({
                            "grupo": "04",
                            "codigo_tipo": "02",
                            "especificacao": f"CDB/Aplicação de Renda Fixa — {nome_fp}",
                            "cnpj_instituicao": cnpj_fp,
                            "saldo_anterior": ant,
                            "saldo_base": base,
                        })

        if rend_exclusiva_match:
            rend_excl = limpar_valor(rend_exclusiva_match.group(1))
            if rend_excl > 0:
                resultado["rendimentos_tributaveis"].append({
                    "codigo": "06",
                    "tipo": "Tributação Exclusiva",
                    "especificacao": "Rendimentos de Aplicações Financeiras (CDB/Renda Fixa)",
                    "valor": rend_excl,
                    "fonte_nome": nome_fp,
                    "fonte_cnpj": cnpj_fp,
                })

        # ── Seção 5 — Conta Corrente ──────────────────────────────────────────
        sec5_match = re.search(
            r"DEPOSITO BANCARIO EM CONTA CORRENTE(.+?)(?=\nPra receber|$)",
            texto, re.DOTALL | re.IGNORECASE
        )
        if sec5_match:
            sec5 = sec5_match.group(1)
            m_tot = re.search(r"TOTAL\s+5[.\s]+([\d.,\s]+)", sec5)
            if m_tot:
                ant, base = _dois_valores(m_tot.group(0))
                if ant > 0 or base > 0:
                    resultado["bens_direitos"].append({
                        "grupo": "06",
                        "codigo_tipo": "99",
                        "especificacao": f"Depósito à Vista (Conta Corrente) — {nome_fp}",
                        "cnpj_instituicao": cnpj_fp,
                        "saldo_anterior": ant,
                        "saldo_base": base,
                    })

        # ── Bradesco Capitalização — Título de Capitalização ──────────────────
        cap_match = re.search(
            r"T[IÍ]TULOS? DE CAPITALIZA[CÇ][AÃ]O.+?"
            r"([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})",
            texto, re.DOTALL | re.IGNORECASE
        )
        if cap_match:
            ant  = limpar_valor(cap_match.group(1))
            base = limpar_valor(cap_match.group(2))
            rend = limpar_valor(cap_match.group(3))
            cnpj_cap_m = re.search(r"CNPJ/MF:\s*([\d./ -]+)", texto)
            cnpj_cap = cnpj_cap_m.group(1).strip() if cnpj_cap_m else ""
            if ant > 0 or base > 0:
                resultado["bens_direitos"].append({
                    "grupo": "99",
                    "codigo_tipo": "99",
                    "especificacao": "Título de Capitalização — Bradesco Capitalização S.A.",
                    "cnpj_instituicao": cnpj_cap,
                    "saldo_anterior": ant,
                    "saldo_base": base,
                })

        return resultado
