"""
📄 Importar Nota de Negociação
Importa PDF automaticamente ou permite lançamento manual na mesma tela.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import tempfile
import os
import pandas as pd
from datetime import date

from modules.nota_negociacao import ler_nota_pdf
from modules.scraper import buscar_info_fundo, buscar_info_acao
from database.db import (
    init_db, inserir_operacao, upsert_ativo,
    inserir_rendimento, inserir_renda_fixa, inserir_cripto,
    get_operacoes, deletar_operacao, get_todos_ativos,
)

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #0d1117; }
h1, h2, h3 { color: #f1f5f9 !important; }
p, li, div { color: #cbd5e1; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f1117 0%, #1a1f2e 100%); border-right: 1px solid #2d3748; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.stButton > button { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white !important; border: none; border-radius: 8px; font-weight: 500; }
.stTabs [data-baseweb="tab-list"] { background: #1a1f2e; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #94a3b8 !important; }
.stTabs [aria-selected="true"] { background: #3b82f6 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📄 Importar Nota de Negociação")
st.markdown("Importe um PDF automaticamente ou use o formulário manual abaixo.")
st.divider()

# ─── Session state ─────────────────────────────────────────────────────────────

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "mostrar_manual" not in st.session_state:
    st.session_state.mostrar_manual = False

# Mensagens pós-gravação
if st.session_state.get("_nota_sucesso"):
    st.success(st.session_state.pop("_nota_sucesso"))
if st.session_state.get("_nota_erros"):
    for erro in st.session_state.pop("_nota_erros"):
        st.error(f"❌ {erro}")

# ─── Seção 1: Upload de PDF ────────────────────────────────────────────────────

uploaded = st.file_uploader(
    "📎 Selecione o PDF da nota de negociação",
    type=["pdf"],
    help="Notas da Nu Invest, XP, Clear e outras corretoras são suportadas.",
    key=f"uploader_{st.session_state.uploader_key}",
)

pdf_processado = False  # True quando PDF foi lido com sucesso e tem operações

if uploaded:
    st.session_state.mostrar_manual = False  # reseta ao fazer novo upload

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.spinner("🔍 Lendo PDF e extraindo operações..."):
        dados_nota = ler_nota_pdf(tmp_path)
    os.unlink(tmp_path)

    if dados_nota.get("erro"):
        st.error(f"❌ {dados_nota['erro']}")
        st.info("💡 Não foi possível ler o PDF. Use o formulário de **Lançamento Manual** abaixo.")
        st.session_state.mostrar_manual = True

    elif not dados_nota["operacoes"]:
        # Mostra debug para ajudar a identificar o formato
        with st.expander("🛠️ Debug — Texto bruto do PDF"):
            st.text(dados_nota.get("texto_bruto", "")[:5000])
        st.warning("⚠️ Nenhuma operação foi extraída do PDF. O formato pode não ser suportado.")
        st.info("💡 Use o formulário de **Lançamento Manual** abaixo.")
        st.session_state.mostrar_manual = True

    else:
        # ── Resumo da nota ──────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**📋 Nota:** `{dados_nota['numero_nota']}`")
        with col2:
            _dp = dados_nota['data_pregao']
            _dp_fmt = (lambda p: f"{p[2]}/{p[1]}/{p[0][2:]}")(_dp.split("-")) if _dp and "-" in _dp else _dp
            st.markdown(f"**📅 Pregão:** `{_dp_fmt}`")
        with col3:
            st.markdown(f"**🏦 Corretora:** `{dados_nota['corretora']}`")
        with col4:
            st.markdown(f"**🔍 Parser:** `{dados_nota.get('parser_usado', '?')}`")

        st.markdown(
            f"**💸 Taxas:** Liquidação R$ `{dados_nota['taxa_liquidacao']:.2f}` · "
            f"Emolumentos R$ `{dados_nota['emolumentos']:.2f}` · "
            f"**Líquido:** R$ `{dados_nota['liquido']:.2f}`"
        )

        with st.expander("🛠️ Debug — Texto bruto do PDF (para novos formatos)"):
            st.text(dados_nota.get("texto_bruto", "")[:5000])

        st.success(f"✅ {len(dados_nota['operacoes'])} operação(ões) encontrada(s)")
        st.markdown("---")

        # ── Operações encontradas ───────────────────────────────────────────
        st.markdown("### 📊 Operações Encontradas")
        st.markdown("*Revise e ajuste os dados antes de confirmar.*")

        operacoes_editadas = []

        for i, op in enumerate(dados_nota["operacoes"]):
            emoji = "🟢" if op["tipo"] == "COMPRA" else "🔴"

            with st.expander(
                f"{emoji} {op['tipo']} · **{op['ticker']}** · "
                f"{int(op['quantidade'])} cotas @ R$ {op['preco_unitario']:.2f}",
                expanded=True
            ):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    ticker = st.text_input("Ticker", value=op["ticker"], key=f"ticker_{i}")
                with c2:
                    tipo_op = st.selectbox("Tipo", ["COMPRA", "VENDA"],
                                           index=0 if op["tipo"] == "COMPRA" else 1,
                                           key=f"tipo_{i}")
                with c3:
                    quantidade = st.number_input("Quantidade", value=float(op["quantidade"]),
                                                 min_value=0.0, key=f"qtd_{i}")
                with c4:
                    preco = st.number_input("Preço Unitário (R$)", value=op["preco_unitario"],
                                            min_value=0.0, format="%.4f", key=f"preco_{i}")

                c5, c6, c7 = st.columns(3)
                with c5:
                    tipo_ativo = st.selectbox(
                        "Tipo de Ativo",
                        ["FII", "FIAGRO", "ACAO", "RENDA_FIXA", "CRIPTO"],
                        index=["FII", "FIAGRO", "ACAO", "RENDA_FIXA", "CRIPTO"].index(
                            op.get("tipo_ativo", "ACAO")
                        ),
                        key=f"tipo_ativo_{i}"
                    )
                with c6:
                    taxas = st.number_input("Taxa rateada (R$)", value=op.get("taxa_rateio", 0.0),
                                            format="%.4f", key=f"taxa_{i}")
                with c7:
                    st.markdown(f"**Valor Total:**\nR$ `{quantidade * preco:.2f}`")

                col_busca, col_info = st.columns([1, 3])
                with col_busca:
                    buscar = st.button(f"🔍 Buscar dados de {ticker}", key=f"buscar_{i}")

                info_fundo = st.session_state.get(f"info_{ticker}", {})

                if buscar:
                    with st.spinner(f"Buscando informações de {ticker}..."):
                        if tipo_ativo in ("FII", "FIAGRO"):
                            info_fundo = buscar_info_fundo(ticker, usar_selenium=True)
                        else:
                            info_fundo = buscar_info_acao(ticker)
                    st.session_state[f"info_{ticker}"] = info_fundo

                if info_fundo:
                    if info_fundo.get("erro"):
                        st.warning(info_fundo["erro"])
                    else:
                        with col_info:
                            st.success(
                                f"✅ **{info_fundo.get('nome', ticker)}** · "
                                f"CNPJ: `{info_fundo.get('cnpj', 'N/A')}` · "
                                f"Admin: {info_fundo.get('administrador', 'N/A')} "
                                f"*(via {info_fundo.get('fonte', '?')})*"
                            )

                operacoes_editadas.append({
                    "ticker": ticker.upper(),
                    "tipo_operacao": tipo_op,
                    "data_operacao": dados_nota["data_pregao"],
                    "quantidade": quantidade,
                    "preco_unitario": preco,
                    "taxas": taxas,
                    "corretora": dados_nota["corretora"],
                    "nota_negociacao": dados_nota["numero_nota"],
                    "origem": "PDF",
                    "tipo_ativo": tipo_ativo,
                    "info_fundo": info_fundo or {},
                })

        # ── Confirmar importação ────────────────────────────────────────────
        st.markdown("---")
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            confirmar = st.button("✅ Gravar Operações", use_container_width=True, type="primary")

        if confirmar:
            sucesso = 0
            duplicatas = 0
            erros = []
            for op in operacoes_editadas:
                try:
                    info = op.get("info_fundo", {})
                    upsert_ativo(
                        ticker=op["ticker"],
                        nome=info.get("nome"),
                        tipo=op["tipo_ativo"],
                        cnpj=info.get("cnpj"),
                        administrador=info.get("administrador"),
                    )
                    inserida = inserir_operacao(
                        ticker=op["ticker"],
                        tipo_operacao=op["tipo_operacao"],
                        data_operacao=op["data_operacao"],
                        quantidade=op["quantidade"],
                        preco_unitario=op["preco_unitario"],
                        taxas=op["taxas"],
                        corretora=op["corretora"],
                        nota_negociacao=op["nota_negociacao"],
                        origem="PDF",
                    )
                    if inserida:
                        sucesso += 1
                    else:
                        duplicatas += 1
                except Exception as e:
                    erros.append(f"{op['ticker']}: {e}")

            for key in list(st.session_state.keys()):
                if key.startswith("info_"):
                    del st.session_state[key]

            msgs = []
            if sucesso:
                msgs.append(f"🎉 {sucesso} operação(ões) gravada(s) com sucesso!")
            if duplicatas:
                msgs.append(f"⚠️ {duplicatas} duplicada(s) ignorada(s).")
            if msgs:
                st.session_state["_nota_sucesso"] = " ".join(msgs)
            if erros:
                st.session_state["_nota_erros"] = erros
            st.session_state.uploader_key += 1
            st.rerun()

        pdf_processado = True  # PDF ok, não mostrar manual automaticamente

# ─── Seção 2: Lançamento Manual ────────────────────────────────────────────────

st.divider()

# Abre automaticamente se o PDF falhou; caso contrário, recolhido
expandir_manual = st.session_state.mostrar_manual

with st.expander("✏️ Lançamento Manual", expanded=expandir_manual):

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Operação (Ação/FII/FIAGRO)",
        "💵 Rendimento",
        "🏦 Renda Fixa",
        "₿ Criptomoeda",
    ])

    # ── Tab 1: Operação ────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### 📈 Nova Operação de Renda Variável")

        c1, c2 = st.columns([2, 1])
        with c1:
            ticker_op = st.text_input("Ticker *", placeholder="Ex: KNCR11, PETR4", key="op_ticker").upper()
        with c2:
            tipo_ativo_op = st.selectbox("Tipo de Ativo *", ["FII", "FIAGRO", "ACAO"], key="op_tipo_ativo")

        c3, c4, c5 = st.columns(3)
        with c3:
            tipo_op_m = st.selectbox("Operação *", ["COMPRA", "VENDA"], key="op_tipo")
        with c4:
            data_op_m = st.date_input("Data *", value=date.today(), key="op_data", format="DD/MM/YYYY")
        with c5:
            corretora_op_m = st.text_input("Corretora", value="Nu Investimentos", key="op_corretora")

        c6, c7, c8 = st.columns(3)
        with c6:
            qtd_op_m = st.number_input("Quantidade *", min_value=1, value=100, key="op_qtd")
        with c7:
            preco_op_m = st.number_input("Preço Unitário (R$) *", min_value=0.01, value=10.00,
                                         format="%.4f", key="op_preco")
        with c8:
            taxas_op_m = st.number_input("Taxas (R$)", min_value=0.0, value=0.0,
                                         format="%.4f", key="op_taxas")

        st.info(f"💰 Valor total: **R$ {qtd_op_m * preco_op_m:.2f}** (+ R$ {taxas_op_m:.2f} em taxas)")

        nota_op_m = st.text_input("Número da Nota (opcional)", key="op_nota")
        obs_op_m = st.text_area("Observação (opcional)", key="op_obs", height=68)

        st.markdown("**🔍 Dados do Ativo** *(opcional — preenche CNPJ e nome automaticamente)*")
        col_b1, col_b2 = st.columns([1, 3])
        with col_b1:
            buscar_op_m = st.button("Buscar na Internet", key="op_buscar")

        info_op_m = st.session_state.get(f"info_op_{ticker_op}", {})

        if buscar_op_m and ticker_op:
            with st.spinner(f"Buscando {ticker_op}..."):
                if tipo_ativo_op in ("FII", "FIAGRO"):
                    info_op_m = buscar_info_fundo(ticker_op)
                else:
                    info_op_m = buscar_info_acao(ticker_op)
            st.session_state[f"info_op_{ticker_op}"] = info_op_m

        if info_op_m and not info_op_m.get("erro"):
            st.success(f"✅ **{info_op_m.get('nome', ticker_op)}** · CNPJ: `{info_op_m.get('cnpj', 'N/A')}`")
        elif info_op_m and info_op_m.get("erro"):
            st.warning(info_op_m["erro"])

        st.markdown("**📝 CNPJ e Nome** *(opcionais)*")
        c_nome, c_cnpj = st.columns(2)
        with c_nome:
            nome_manual_m = st.text_input("Nome do Fundo/Empresa", key="op_nome_manual",
                                          value=info_op_m.get("nome", "") if info_op_m else "")
        with c_cnpj:
            cnpj_manual_m = st.text_input("CNPJ", key="op_cnpj_manual",
                                          value=info_op_m.get("cnpj", "") if info_op_m else "",
                                          placeholder="00.000.000/0000-00")

        st.markdown("---")
        if st.button("💾 Salvar Operação", key="btn_salvar_op", type="primary"):
            if not ticker_op:
                st.error("❌ Informe o ticker.")
            else:
                try:
                    nome_final = nome_manual_m if nome_manual_m else (info_op_m.get("nome") if info_op_m else None)
                    cnpj_final = cnpj_manual_m if cnpj_manual_m else (info_op_m.get("cnpj") if info_op_m else None)
                    upsert_ativo(ticker=ticker_op, nome=nome_final, tipo=tipo_ativo_op,
                                 cnpj=cnpj_final,
                                 administrador=info_op_m.get("administrador") if info_op_m else None)
                    inserir_operacao(ticker=ticker_op, tipo_operacao=tipo_op_m,
                                     data_operacao=str(data_op_m), quantidade=qtd_op_m,
                                     preco_unitario=preco_op_m, taxas=taxas_op_m,
                                     corretora=corretora_op_m, nota_negociacao=nota_op_m or None,
                                     origem="MANUAL", observacao=obs_op_m or None)
                    st.success(f"✅ {tipo_op_m} de {qtd_op_m}x {ticker_op} salva!")
                except Exception as e:
                    st.error(f"❌ Erro: {e}")

    # ── Tab 2: Rendimento ──────────────────────────────────────────────────────
    with tab2:
        st.markdown("### 💵 Registrar Rendimento (Dividendo / Rendimento FII)")

        ativos = get_todos_ativos()
        tickers_lista = [a["ticker"] for a in ativos] if ativos else []

        c1, c2 = st.columns(2)
        with c1:
            if tickers_lista:
                ticker_rend = st.selectbox("Ticker *", tickers_lista, key="rend_ticker")
            else:
                ticker_rend = st.text_input("Ticker *", key="rend_ticker_manual").upper()
        with c2:
            tipo_rend = st.selectbox("Tipo", ["RENDIMENTO", "DIVIDENDO", "JCP"], key="rend_tipo")

        c3, c4, c5 = st.columns(3)
        with c3:
            data_pag = st.date_input("Data de Pagamento *", key="rend_data_pag", format="DD/MM/YYYY")
        with c4:
            data_com = st.date_input("Data COM", key="rend_data_com", value=None, format="DD/MM/YYYY")
        with c5:
            isento = st.checkbox("Isento de IR", value=True, key="rend_isento",
                                 help="FIIs e FIAGROs para PF geralmente são isentos.")

        c6, c7 = st.columns(2)
        with c6:
            val_cota = st.number_input("Valor por Cota (R$) *", min_value=0.0001,
                                       value=0.10, format="%.4f", key="rend_val_cota")
        with c7:
            qtd_cotas = st.number_input("Quantidade de Cotas *", min_value=0.0,
                                        value=100.0, key="rend_qtd")

        st.info(f"💰 Total recebido: **R$ {val_cota * qtd_cotas:.2f}**")

        if st.button("💾 Salvar Rendimento", key="btn_rend", type="primary"):
            try:
                inserir_rendimento(
                    ticker=ticker_rend, data_pagamento=str(data_pag),
                    valor_por_cota=val_cota, quantidade_cotas=qtd_cotas,
                    data_com=str(data_com) if data_com else None,
                    tipo=tipo_rend, isento_ir=isento,
                )
                st.success(f"✅ Rendimento de R$ {val_cota * qtd_cotas:.2f} registrado!")
            except Exception as e:
                st.error(f"❌ Erro: {e}")

    # ── Tab 3: Renda Fixa ──────────────────────────────────────────────────────
    with tab3:
        st.markdown("### 🏦 Novo Ativo de Renda Fixa")

        c1, c2 = st.columns(2)
        with c1:
            descricao_rf = st.text_input("Descrição *", placeholder="Ex: CDB Banco X 120% CDI", key="rf_desc")
        with c2:
            tipo_rf = st.selectbox("Tipo *", ["CDB", "LCI", "LCA", "TESOURO_SELIC",
                                               "TESOURO_IPCA", "TESOURO_PREFIXADO",
                                               "DEBENTURE", "CRI", "CRA", "OUTRO"], key="rf_tipo")

        c3, c4 = st.columns(2)
        with c3:
            instituicao_rf = st.text_input("Instituição *", placeholder="Ex: Nubank", key="rf_inst")
        with c4:
            cnpj_rf = st.text_input("CNPJ da Instituição", placeholder="00.000.000/0000-00", key="rf_cnpj")

        c5, c6 = st.columns(2)
        with c5:
            data_aplic = st.date_input("Data de Aplicação *", key="rf_data_aplic", format="DD/MM/YYYY")
        with c6:
            data_venc = st.date_input("Data de Vencimento", key="rf_data_venc", value=None, format="DD/MM/YYYY")

        c7, c8, c9 = st.columns(3)
        with c7:
            val_aplic = st.number_input("Valor Aplicado (R$) *", min_value=0.01,
                                        value=1000.00, format="%.2f", key="rf_val_aplic")
        with c8:
            val_atual = st.number_input("Valor Atual (R$)", min_value=0.0, value=0.0,
                                        format="%.2f", key="rf_val_atual",
                                        help="Deixe 0 para usar o valor aplicado")
        with c9:
            taxa_rf = st.text_input("Taxa Contratada", placeholder="Ex: 120% CDI", key="rf_taxa")

        if st.button("💾 Salvar Renda Fixa", key="btn_rf", type="primary"):
            if not descricao_rf or not instituicao_rf:
                st.error("❌ Preencha descrição e instituição.")
            else:
                try:
                    inserir_renda_fixa(
                        descricao=descricao_rf, tipo=tipo_rf, instituicao=instituicao_rf,
                        cnpj_instituicao=cnpj_rf or None, data_aplicacao=str(data_aplic),
                        data_vencimento=str(data_venc) if data_venc else None,
                        valor_aplicado=val_aplic, taxa_contratada=taxa_rf or None,
                        valor_atual=val_atual if val_atual > 0 else None,
                    )
                    st.success(f"✅ {tipo_rf} de R$ {val_aplic:.2f} em {instituicao_rf} salvo!")
                except Exception as e:
                    st.error(f"❌ Erro: {e}")

    # ── Tab 4: Cripto ──────────────────────────────────────────────────────────
    with tab4:
        st.markdown("### ₿ Nova Operação de Criptomoeda")

        c1, c2, c3 = st.columns(3)
        with c1:
            moeda = st.text_input("Moeda *", placeholder="Ex: BTC, ETH, SOL",
                                   key="cripto_moeda").upper()
        with c2:
            tipo_cripto = st.selectbox("Operação *", ["COMPRA", "VENDA"], key="cripto_tipo")
        with c3:
            data_cripto = st.date_input("Data *", key="cripto_data", format="DD/MM/YYYY")

        c4, c5, c6 = st.columns(3)
        with c4:
            qtd_cripto = st.number_input("Quantidade *", min_value=0.000001,
                                         value=0.001, format="%.8f", key="cripto_qtd")
        with c5:
            preco_cripto = st.number_input("Preço (R$/unidade) *", min_value=0.01,
                                           value=100000.0, format="%.2f", key="cripto_preco")
        with c6:
            exchange = st.text_input("Exchange", placeholder="Binance, Coinbase...", key="cripto_exchange")

        taxa_cripto = st.number_input("Taxa (R$)", min_value=0.0, value=0.0,
                                       format="%.4f", key="cripto_taxa")
        st.info(f"💰 Valor total: **R$ {qtd_cripto * preco_cripto:.2f}**")

        if st.button("💾 Salvar Operação Cripto", key="btn_cripto", type="primary"):
            if not moeda:
                st.error("❌ Informe a moeda.")
            else:
                try:
                    inserir_cripto(
                        moeda=moeda, tipo_operacao=tipo_cripto,
                        data_operacao=str(data_cripto), quantidade=qtd_cripto,
                        preco_unitario_brl=preco_cripto,
                        exchange=exchange or None, taxa=taxa_cripto,
                    )
                    st.success(f"✅ {tipo_cripto} de {qtd_cripto} {moeda} salva!")
                except Exception as e:
                    st.error(f"❌ Erro: {e}")

# ─── Seção 3: Histórico ────────────────────────────────────────────────────────

st.divider()
with st.expander("📋 Histórico de Operações"):
    ativos_todos = get_todos_ativos()
    filtro = st.selectbox(
        "Filtrar por ticker",
        ["Todos"] + [a["ticker"] for a in ativos_todos],
        key="hist_nota_filtro"
    )
    operacoes_hist = get_operacoes(filtro if filtro != "Todos" else None)

    if not operacoes_hist:
        st.info("📂 Nenhuma operação encontrada.")
    else:
        df_hist = pd.DataFrame([{
            "ID":         op["id"],
            "Data":       (lambda d: f"{d[2]}/{d[1]}/{d[0][2:]}")(op["data_operacao"].split("-")) if op.get("data_operacao") else "—",
            "Ticker":     op["ticker"],
            "Tipo":       op["tipo_operacao"],
            "Qtd":        op["quantidade"],
            "Preço (R$)": f"{op['preco_unitario']:.4f}",
            "Total (R$)": f"{op['valor_total']:.2f}",
            "Taxas (R$)": f"{op['taxas']:.4f}",
            "Corretora":  op.get("corretora") or "—",
            "Nota":       op.get("nota_negociacao") or "—",
            "Origem":     op.get("origem") or "MANUAL",
        } for op in operacoes_hist])

        st.dataframe(df_hist, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("**🗑️ Excluir operação**")
        col_del1, col_del2 = st.columns([1, 3])
        with col_del1:
            op_id_del = st.number_input("ID a excluir", min_value=1, key="nota_del_id")
        with col_del2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("❌ Excluir", key="nota_btn_del"):
                deletar_operacao(int(op_id_del))
                st.success(f"Operação #{op_id_del} excluída.")
                st.rerun()
