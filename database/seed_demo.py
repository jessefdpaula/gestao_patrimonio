"""
Dados de demonstração para o modo sessão (Streamlit Cloud).

Todos os dados são 100% fictícios:
  - Nomes, CPFs e CNPJs não correspondem a pessoas ou empresas reais
  - Tickers são reais (mercado público), mas quantidades/preços são exemplos
  - Nenhum dado pessoal real é utilizado

Chamado automaticamente por init_db() quando o banco de sessão está vazio.
"""

from datetime import datetime
from database.db import (
    upsert_ativo, inserir_operacao, inserir_rendimento,
    inserir_informe_tributavel, inserir_informe_isento,
    inserir_renda_fixa, marcar_declarado, _db,
)


TITULAR_DEMO = {
    "nome": "João da Silva",
    "cpf":  "123.456.789-09",   # CPF fictício — não pertence a nenhuma pessoa real
}


def seed_demo():
    """Popula o banco de sessão com dados fictícios de demonstração."""

    # ── Ativos ────────────────────────────────────────────────────────────────
    ativos = [
        ("MXRF11", "Maxi Renda FII",          "FII"),
        ("HGLG11", "CSHG Logística FII",      "FII"),
        ("SNAG11", "Suno Agro FIAgro",        "FIAGRO"),
        ("PETR4",  "Petróleo Brasileiro S.A.", "ACAO"),
        ("KLBN4",  "Klabin S.A.",              "ACAO"),
    ]
    for ticker, nome, tipo in ativos:
        upsert_ativo(ticker, nome=nome, tipo=tipo)

    # ── Operações de compra ───────────────────────────────────────────────────
    operacoes = [
        # ticker,   tipo,     data,         qtd,   preço,   taxas, corretora
        ("MXRF11", "COMPRA", "2024-02-10",  200,   9.75,   1.20, "Demo Invest"),
        ("MXRF11", "COMPRA", "2024-07-15",  100,   10.10,  0.80, "Demo Invest"),
        ("HGLG11", "COMPRA", "2024-03-20",   40,  158.50,  1.50, "Demo Invest"),
        ("HGLG11", "COMPRA", "2024-09-05",   20,  162.00,  0.90, "Demo Invest"),
        ("SNAG11", "COMPRA", "2024-05-12",  150,    9.30,  1.10, "Demo Invest"),
        ("PETR4",  "COMPRA", "2024-01-08",  300,   35.40,  2.00, "Demo Invest"),
        ("PETR4",  "VENDA",  "2024-11-20",  100,   39.80,  1.50, "Demo Invest"),
        ("KLBN4",  "COMPRA", "2024-04-18",  500,   21.20,  1.80, "Demo Invest"),
        ("KLBN4",  "COMPRA", "2024-10-03",  200,   22.50,  1.00, "Demo Invest"),
    ]
    for ticker, tipo, data, qtd, preco, taxas, corr in operacoes:
        inserir_operacao(
            ticker=ticker, tipo_operacao=tipo, data_operacao=data,
            quantidade=qtd, preco_unitario=preco, taxas=taxas,
            corretora=corr, origem="DEMO",
        )

    # ── Rendimentos (FIIs e FIAgro — isentos) ────────────────────────────────
    rendimentos = [
        # ticker,   data_pag,     vl/cota, qtd,   tipo
        ("MXRF11", "2025-01-15",  0.10,   300,  "RENDIMENTO"),
        ("MXRF11", "2025-02-14",  0.10,   300,  "RENDIMENTO"),
        ("MXRF11", "2025-03-14",  0.11,   300,  "RENDIMENTO"),
        ("HGLG11", "2025-01-10",  1.25,    60,  "RENDIMENTO"),
        ("HGLG11", "2025-02-10",  1.25,    60,  "RENDIMENTO"),
        ("HGLG11", "2025-03-10",  1.30,    60,  "RENDIMENTO"),
        ("SNAG11", "2025-01-20",  0.09,   150,  "RENDIMENTO"),
        ("SNAG11", "2025-02-20",  0.09,   150,  "RENDIMENTO"),
        ("SNAG11", "2025-03-20",  0.10,   150,  "RENDIMENTO"),
        ("PETR4",  "2025-03-05",  0.80,   200,  "DIVIDENDO"),
        ("KLBN4",  "2025-02-28",  0.12,   700,  "DIVIDENDO"),
    ]
    for ticker, data, vl_cota, qtd, tipo in rendimentos:
        isento = tipo in ("RENDIMENTO",)  # FII/FIAgro isentos; dividendos também isentos desde 1996
        inserir_rendimento(
            ticker=ticker, data_pagamento=data,
            valor_por_cota=vl_cota, quantidade_cotas=qtd,
            tipo=tipo, isento_ir=True,
        )

    # ── Renda fixa ───────────────────────────────────────────────────────────
    inserir_renda_fixa(
        descricao="CDB Banco Demo",
        tipo="CDB",
        instituicao="Banco Demo S.A.",
        cnpj_instituicao="00.000.001/0001-91",   # CNPJ fictício
        data_aplicacao="2024-06-01",
        data_vencimento="2026-06-01",
        valor_aplicado=10000.00,
        taxa_contratada="CDI + 0,5%",
        valor_atual=10850.00,
    )
    inserir_renda_fixa(
        descricao="LCI Banco Demo",
        tipo="LCI",
        instituicao="Banco Demo S.A.",
        cnpj_instituicao="00.000.001/0001-91",
        data_aplicacao="2024-09-15",
        data_vencimento="2025-09-15",
        valor_aplicado=5000.00,
        taxa_contratada="90% do CDI",
        valor_atual=5320.00,
    )

    # ── Informes de rendimentos 2025 ──────────────────────────────────────────

    # Tributáveis
    inserir_informe_tributavel(
        ano_calendario="2025",
        fonte_nome="Banco Demo S.A.",
        fonte_cnpj="00.000.001/0001-91",
        codigo="06",
        tipo="Rendimentos de Aplicações Financeiras",
        especificacao="CDB — rendimento do período",
        valor=850.00,
    )

    # Isentos
    for espec, valor in [
        ("Caderneta de Poupança",               420.00),
        ("Dividendos — PETR4",                  160.00),
        ("Dividendos — KLBN4",                   84.00),
        ("Rendimentos FII — MXRF11",             99.00),
        ("Rendimentos FII — HGLG11",            228.00),
        ("Rendimentos FIAgro — SNAG11",          42.00),
        ("LCI — Banco Demo S.A.",               210.00),
    ]:
        inserir_informe_isento(
            ano_calendario="2025",
            fonte_nome="Banco Demo S.A.",
            fonte_cnpj="00.000.001/0001-91",
            codigo="12",
            especificacao=espec,
            valor=valor,
        )

    # ── IRPF — alguns itens já "declarados" como exemplo ─────────────────────
    marcar_declarado("2025", "bens",      "MXRF11")
    marcar_declarado("2025", "bens",      "HGLG11")
    marcar_declarado("2025", "rend_fii",  "MXRF11")
