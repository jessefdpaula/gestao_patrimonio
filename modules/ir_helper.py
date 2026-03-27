"""
Módulo auxiliar para declaração do Imposto de Renda (IRPF).
Gera os dados necessários para preencher a declaração:
  - Bens e Direitos (Patrimônio)
  - Rendimentos Isentos (FIIs, FIAGROs)
  - Rendimentos Tributáveis
  - Ganho de Capital (venda de ativos)
"""

from datetime import datetime
from database.db import (
    get_carteira_completa, get_operacoes, get_rendimentos,
    get_renda_fixa, get_cripto_posicao, get_todos_ativos,
    get_informe_tributaveis, get_informe_isentos
)


# ─── Códigos IRPF ─────────────────────────────────────────────────────────────

CODIGOS_IRPF = {
    "FII":       {"grupo": "07", "codigo": "03", "desc": "Fundos de Investimento Imobiliário (FII)"},
    "FIAGRO":    {"grupo": "07", "codigo": "02", "desc": "Fundos de Investimento nas Cadeias Produtivas Agroindustriais (FIAGRO)"},
    "ACAO":      {"grupo": "03", "codigo": "01", "desc": "Ações (ordinárias, preferenciais, etc.)"},
    "CDB":       {"grupo": "04", "codigo": "01", "desc": "Depósitos em contas bancárias - CDB"},
    "LCI":       {"grupo": "04", "codigo": "02", "desc": "LCI – Letra de Crédito Imobiliário"},
    "LCA":       {"grupo": "04", "codigo": "02", "desc": "LCA – Letra de Crédito do Agronegócio"},
    "TESOURO":   {"grupo": "04", "codigo": "04", "desc": "Títulos do Tesouro Nacional"},
    "CRIPTO":    {"grupo": "08", "codigo": "01", "desc": "Criptoativos (Bitcoin, Ethereum, etc.)"},
}

# Corretora padrão — configure com o CNPJ da sua corretora principal
CORRETORA_PADRAO = {
    "nome": "Minha Corretora",
    "cnpj": ""
}


# ─── Bens e Direitos ──────────────────────────────────────────────────────────

def gerar_bens_e_direitos(ano_base: int = None) -> list:
    """
    Gera lista de itens para preencher 'Bens e Direitos' no IRPF.
    Retorna dados na estrutura esperada pela Receita Federal.
    """
    if not ano_base:
        ano_base = datetime.today().year - 1

    ano_anterior = ano_base - 1
    bens = []

    # ── Ações, FIIs e FIAGROs ─────────────────────────────────────────────────
    carteira = get_carteira_completa()
    ativos_info = {a["ticker"]: a for a in get_todos_ativos()}

    for posicao in carteira:
        ticker = posicao["ticker"]
        tipo = posicao.get("tipo", "ACAO")
        cod_irpf = CODIGOS_IRPF.get(tipo, CODIGOS_IRPF["ACAO"])
        ativo = ativos_info.get(ticker, {})

        # Calcula valor em 31/12 do ano anterior e 31/12 do ano base
        val_ano_anterior = _calcular_custo_em_data(
            ticker, f"{ano_anterior}-12-31"
        )
        val_ano_base = _calcular_custo_em_data(
            ticker, f"{ano_base}-12-31"
        )

        # Ignora ativos sem posição em nenhum dos dois anos (ex: comprado em 2026)
        if val_ano_anterior == 0 and val_ano_base == 0:
            continue

        cnpj_fundo = ativo.get("cnpj") or ""
        nome_fundo = ativo.get("nome") or ticker
        corretora = CORRETORA_PADRAO  # Pode ser parametrizado por operação futuramente

        discriminacao = (
            f"Cotas de {nome_fundo} ({ticker}) distribuídas na corretora "
            f"{corretora['nome']}, CNPJ {corretora['cnpj']}."
        )
        if cnpj_fundo:
            discriminacao = (
                f"Cotas de {nome_fundo} ({ticker}), CNPJ do fundo {cnpj_fundo}, "
                f"distribuídas na corretora {corretora['nome']}, CNPJ {corretora['cnpj']}."
            )

        bens.append({
            "grupo": cod_irpf["grupo"],
            "codigo": cod_irpf["codigo"],
            "descricao_codigo": cod_irpf["desc"],
            "ticker": ticker,
            "nome": nome_fundo,
            "cnpj_fundo": cnpj_fundo,
            "localizacao": "105 - Brasil",
            "discriminacao": discriminacao,
            "valor_ano_anterior": round(val_ano_anterior, 2),
            "valor_ano_base": round(val_ano_base, 2),
            "tipo": tipo,
        })

    # ── Renda Fixa ────────────────────────────────────────────────────────────
    renda_fixa = get_renda_fixa()
    for rf in renda_fixa:
        tipo_rf = rf["tipo"].upper()
        cod_irpf = CODIGOS_IRPF.get(tipo_rf, {"grupo": "04", "codigo": "01", "desc": rf["tipo"]})
        bens.append({
            "grupo": cod_irpf["grupo"],
            "codigo": cod_irpf["codigo"],
            "descricao_codigo": cod_irpf["desc"],
            "ticker": rf["tipo"],
            "nome": rf["descricao"],
            "cnpj_fundo": rf.get("cnpj_instituicao", ""),
            "localizacao": "105 - Brasil",
            "discriminacao": (
                f"{rf['tipo']} emitido por {rf['instituicao']} "
                f"(CNPJ {rf.get('cnpj_instituicao', 'N/A')}), "
                f"aplicado em {rf['data_aplicacao']}, "
                f"taxa: {rf.get('taxa_contratada', 'N/A')}."
            ),
            "valor_ano_anterior": 0.0,
            "valor_ano_base": round(rf["valor_atual"] or rf["valor_aplicado"], 2),
            "tipo": tipo_rf,
        })

    # ── Criptomoedas ──────────────────────────────────────────────────────────
    cripto_posicoes = get_cripto_posicao()
    for cripto in cripto_posicoes:
        bens.append({
            "grupo": "08",
            "codigo": "01",
            "descricao_codigo": "Criptoativos",
            "ticker": cripto["moeda"],
            "nome": cripto["moeda"],
            "cnpj_fundo": "",
            "localizacao": "105 - Brasil",
            "discriminacao": (
                f"{cripto['quantidade']:.8f} {cripto['moeda']} "
                f"adquiridos ao preço médio de R$ {cripto['preco_medio']:.2f}."
            ),
            "valor_ano_anterior": 0.0,
            "valor_ano_base": round(cripto["custo_total"], 2),
            "tipo": "CRIPTO",
        })

    return bens


def _calcular_custo_em_data(ticker: str, data_limite: str) -> float:
    """
    Calcula o custo de aquisição acumulado até uma data específica.
    """
    operacoes = get_operacoes(ticker)
    quantidade = 0.0
    custo_total = 0.0

    for op in sorted(operacoes, key=lambda x: x["data_operacao"]):
        if op["data_operacao"] > data_limite:
            break
        if op["tipo_operacao"] == "COMPRA":
            custo_total += op["valor_total"] + op.get("taxas", 0)
            quantidade += op["quantidade"]
        elif op["tipo_operacao"] == "VENDA" and quantidade > 0:
            pm = custo_total / quantidade
            custo_total -= pm * op["quantidade"]
            quantidade -= op["quantidade"]

    return max(custo_total, 0.0)


# ─── Rendimentos Isentos (FIIs e FIAGROs) ────────────────────────────────────

def gerar_rendimentos_isentos(ano_base: int = None) -> list:
    """
    Gera dados para a ficha 'Rendimentos Isentos e Não Tributáveis'.
    FIIs e FIAGROs: Código 26 - Outros (rendimentos de FII/FIAGRO isentos para PF).
    """
    if not ano_base:
        ano_base = datetime.today().year - 1

    rendimentos = get_rendimentos()
    ativos_info = {a["ticker"]: a for a in get_todos_ativos()}
    resultado = {}

    for rend in rendimentos:
        # Filtra pelo ano base
        if not rend["data_pagamento"].startswith(str(ano_base)):
            continue
        if not rend.get("isento_ir", 1):
            continue

        ticker = rend["ticker"]
        ativo = ativos_info.get(ticker, {})

        if ticker not in resultado:
            resultado[ticker] = {
                "ticker": ticker,
                "nome": ativo.get("nome", ticker),
                "cnpj_fonte": ativo.get("cnpj", ""),
                "tipo": ativo.get("tipo", "FII"),
                "total_recebido": 0.0,
                "codigo_ficha": "26",
                "desc_ficha": "Outros (rendimentos isentos FII/FIAGRO)",
            }
        resultado[ticker]["total_recebido"] += rend["valor_total"]

    return list(resultado.values())


# ─── Ganho de Capital ─────────────────────────────────────────────────────────

def gerar_ganho_capital(ano_base: int = None) -> list:
    """
    Calcula ganho/perda de capital em operações de venda.
    FIIs: tributação de 20% sobre o lucro.
    Ações: isenção para vendas até R$20k/mês, 15% acima disso.
    FIAGROs: tributação específica.
    """
    if not ano_base:
        ano_base = datetime.today().year - 1

    operacoes = get_operacoes()
    ativos_info = {a["ticker"]: a for a in get_todos_ativos()}
    vendas_por_mes = {}  # {AAAA-MM: {ticker: [ops]}}

    for op in operacoes:
        if op["tipo_operacao"] != "VENDA":
            continue
        if not op["data_operacao"].startswith(str(ano_base)):
            continue

        mes = op["data_operacao"][:7]  # AAAA-MM
        if mes not in vendas_por_mes:
            vendas_por_mes[mes] = []
        vendas_por_mes[mes].append(op)

    resultados = []

    for mes, vendas in sorted(vendas_por_mes.items()):
        total_vendido_acoes = sum(
            v["valor_total"] for v in vendas
            if ativos_info.get(v["ticker"], {}).get("tipo", "ACAO") == "ACAO"
        )

        for op in vendas:
            ticker = op["ticker"]
            ativo = ativos_info.get(ticker, {})
            tipo = ativo.get("tipo", "ACAO")

            pm_na_venda = _calcular_custo_em_data(ticker, op["data_operacao"])
            # Estima PM pela quantidade vendida
            posicao_antes = _calcular_custo_em_data(
                ticker,
                (datetime.strptime(op["data_operacao"], "%Y-%m-%d") -
                 __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")
            )
            qtd_antes = _get_quantidade_em_data(ticker, op["data_operacao"])
            pm = (posicao_antes / qtd_antes) if qtd_antes > 0 else 0

            custo_venda = pm * op["quantidade"]
            ganho = op["valor_total"] - custo_venda - op.get("taxas", 0)

            # Alíquota
            isento = False
            aliquota = 0.0

            if tipo == "ACAO":
                if total_vendido_acoes <= 20000:
                    isento = True
                    aliquota = 0.0
                else:
                    aliquota = 0.15  # swing trade
            elif tipo == "FII":
                aliquota = 0.20
            elif tipo == "FIAGRO":
                aliquota = 0.15  # regra geral FIAGRO

            ir_devido = max(0, ganho * aliquota) if not isento else 0.0

            resultados.append({
                "ticker": ticker,
                "mes": mes,
                "tipo": tipo,
                "quantidade_vendida": op["quantidade"],
                "valor_venda": op["valor_total"],
                "custo_aquisicao": round(custo_venda, 2),
                "ganho_liquido": round(ganho, 2),
                "isento": isento,
                "aliquota_pct": aliquota * 100,
                "ir_devido": round(ir_devido, 2),
                "total_vendas_acoes_mes": round(total_vendido_acoes, 2)
                    if tipo == "ACAO" else None,
            })

    return resultados


def _get_quantidade_em_data(ticker: str, data_limite: str) -> float:
    """Retorna quantidade de um ativo em uma data."""
    operacoes = get_operacoes(ticker)
    quantidade = 0.0
    for op in sorted(operacoes, key=lambda x: x["data_operacao"]):
        if op["data_operacao"] >= data_limite:
            break
        if op["tipo_operacao"] == "COMPRA":
            quantidade += op["quantidade"]
        elif op["tipo_operacao"] == "VENDA":
            quantidade -= op["quantidade"]
    return max(quantidade, 0.0)


# ─── Rendimentos Tributáveis (Informes) ───────────────────────────────────────

def gerar_rendimentos_tributaveis_informe(ano_base: int = None) -> list:
    """
    Retorna rendimentos tributáveis importados de informes de rendimentos (PDFs).
    Agrupa por fonte pagadora.
    """
    if not ano_base:
        ano_base = datetime.today().year - 1

    registros = get_informe_tributaveis(str(ano_base))
    agrupado = {}

    for r in registros:
        chave = r["fonte_cnpj"] or r["fonte_nome"] or "desconhecida"
        if chave not in agrupado:
            agrupado[chave] = {
                "fonte_nome": r["fonte_nome"] or "Não identificada",
                "fonte_cnpj": r["fonte_cnpj"] or "",
                "ano_calendario": r["ano_calendario"],
                "itens": [],
                "total": 0.0,
            }
        agrupado[chave]["itens"].append({
            "codigo": r["codigo"],
            "tipo": r["tipo"],
            "especificacao": r["especificacao"],
            "valor": r["valor"],
        })
        agrupado[chave]["total"] += r["valor"]

    return list(agrupado.values())


def gerar_rendimentos_isentos_informe(ano_base: int = None) -> list:
    """
    Retorna rendimentos isentos importados de informes de rendimentos (PDFs).
    Agrupa por fonte pagadora.
    """
    if not ano_base:
        ano_base = datetime.today().year - 1

    registros = get_informe_isentos(str(ano_base))
    agrupado = {}

    for r in registros:
        chave = r["fonte_cnpj"] or r["fonte_nome"] or "desconhecida"
        if chave not in agrupado:
            agrupado[chave] = {
                "fonte_nome": r["fonte_nome"] or "Não identificada",
                "fonte_cnpj": r["fonte_cnpj"] or "",
                "ano_calendario": r["ano_calendario"],
                "itens": [],
                "total": 0.0,
            }
        agrupado[chave]["itens"].append({
            "codigo": r["codigo"],
            "especificacao": r["especificacao"],
            "valor": r["valor"],
        })
        agrupado[chave]["total"] += r["valor"]

    return list(agrupado.values())


# ─── Resumo geral para exportação ─────────────────────────────────────────────

def gerar_relatorio_ir(ano_base: int = None) -> dict:
    """Retorna todos os dados necessários para o IRPF de um ano."""
    if not ano_base:
        ano_base = datetime.today().year - 1
    return {
        "ano_base": ano_base,
        "bens_e_direitos": gerar_bens_e_direitos(ano_base),
        "rendimentos_isentos": gerar_rendimentos_isentos(ano_base),
        "rendimentos_tributaveis_informe": gerar_rendimentos_tributaveis_informe(ano_base),
        "rendimentos_isentos_informe": gerar_rendimentos_isentos_informe(ano_base),
        "ganho_capital": gerar_ganho_capital(ano_base),
    }
