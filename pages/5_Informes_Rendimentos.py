"""
📋 Informes de Rendimentos
Lê PDFs de Informes de Rendimentos Financeiros (IR) e exibe os dados
organizados por seção, prontos para consulta e registro no app.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import tempfile
import os

from database.db import (
    init_db, upsert_ativo, inserir_renda_fixa,
    inserir_cripto, get_renda_fixa,
    inserir_informe_tributavel, inserir_informe_isento,
    get_informe_tributaveis, get_informe_isentos,
    deletar_informe_tributavel, deletar_informe_isento
)
from modules.informe_rendimentos import ler_informe_rendimentos

init_db()

# ─── CSS ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #0d1117; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f1117 0%, #1a1f2e 100%); border-right: 1px solid #2d3748; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
h1, h2, h3 { color: #f1f5f9 !important; }
p, li, div { color: #cbd5e1; }
.stButton > button { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white !important; border: none; border-radius: 8px; font-weight: 500; font-family: 'Space Grotesk', sans-serif; }
.stTabs [data-baseweb="tab-list"] { background: #1a1f2e; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #94a3b8 !important; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #3b82f6 !important; color: white !important; }
[data-testid="metric-container"] { background: linear-gradient(135deg, #1a1f2e, #16213e); border: 1px solid #2d3748; border-radius: 12px; padding: 14px; }
[data-testid="metric-container"] label { color: #94a3b8 !important; font-size: 11px !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.4rem !important; font-weight: 700 !important; font-family: 'JetBrains Mono', monospace !important; }
.fonte-card { background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
.fonte-nome { font-weight: 600; color: #f1f5f9; font-size: 14px; }
.fonte-cnpj { font-family: 'JetBrains Mono', monospace; color: #60a5fa; font-size: 12px; margin-top: 3px; }
.section-box { background: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 18px; margin-bottom: 16px; }
.tag { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; }
.tag-trib  { background: #3a1a1a; color: #f87171; }
.tag-isento { background: #1a3a2a; color: #4ade80; }
.tag-bem   { background: #1e3a5f; color: #60a5fa; }
.tag-cripto { background: #3a2a1a; color: #fb923c; }
.aviso { background: #1a2a1a; border: 1px solid #2d4a2d; border-radius: 8px; padding: 12px 16px; color: #4ade80; font-size: 13px; margin: 8px 0; }
.alerta { background: #2a1a1a; border: 1px solid #4a2d2d; border-radius: 8px; padding: 12px 16px; color: #f87171; font-size: 13px; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

# ─── Cabeçalho ───────────────────────────────────────────────────────────────

st.markdown("# 📋 Informes de Rendimentos")
st.markdown("Importe o PDF do informe de rendimentos para visualizar e registrar os dados no app.")
st.divider()

# ─── Mensagem pós-gravação ────────────────────────────────────────────────────

if "informe_uploader_key" not in st.session_state:
    st.session_state.informe_uploader_key = 0

if st.session_state.get("_informe_sucesso"):
    msg = st.session_state.pop("_informe_sucesso")
    st.success(msg)
if st.session_state.get("_informe_erros"):
    for erro in st.session_state.pop("_informe_erros"):
        st.error(f"❌ {erro}")

# ─── Upload ──────────────────────────────────────────────────────────────────

col_up, col_info = st.columns([2, 1])
with col_up:
    uploaded = st.file_uploader(
        "📎 Selecione o PDF do Informe de Rendimentos",
        type=["pdf"],
        help="Informes do Mercado Pago, Nubank, XP, BTG, Rico, Clear e outras instituições.",
        key=f"informe_uploader_{st.session_state.informe_uploader_key}",
    )
with col_info:
    st.markdown("""
    <div class="section-box" style="margin-top:28px;">
        <div style="font-size:13px; color:#94a3b8;">
            <strong style="color:#f1f5f9;">O que é extraído:</strong><br><br>
            🏦 Fontes pagadoras e CNPJs<br>
            💰 Rendimentos tributáveis<br>
            ✅ Rendimentos isentos (LCI, LCA...)<br>
            📁 Bens e Direitos (saldos)<br>
            ₿ Criptomoedas
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─── Histórico de Informes Gravados (sempre visível) ─────────────────────────

with st.expander("📋 Histórico de Informes Gravados"):
    anos_disponiveis = sorted(
        {r["ano_calendario"] for r in get_informe_tributaveis() + get_informe_isentos()},
        reverse=True
    )

    if not anos_disponiveis:
        st.info("📂 Nenhum informe gravado ainda.")
    else:
        ano_filtro = st.selectbox("Ano-calendário", anos_disponiveis, key="hist_inf_ano")

        htab1, htab2 = st.tabs(["💸 Tributáveis", "✅ Isentos"])

        with htab1:
            trib_hist = get_informe_tributaveis(ano_filtro)
            if not trib_hist:
                st.info("Nenhum rendimento tributável gravado para este ano.")
            else:
                df_trib_h = pd.DataFrame([{
                    "ID":            r["id"],
                    "Ano":           r["ano_calendario"],
                    "Fonte":         r["fonte_nome"] or "—",
                    "CNPJ":          r["fonte_cnpj"] or "—",
                    "Código":        r["codigo"] or "—",
                    "Tipo":          r["tipo"] or "—",
                    "Especificação": r["especificacao"] or "—",
                    "Valor (R$)":    r["valor"],
                } for r in trib_hist])
                st.dataframe(df_trib_h, hide_index=True, use_container_width=True)

                st.markdown("---")
                st.markdown("**🗑️ Excluir item tributável**")
                col_dt1, col_dt2 = st.columns([1, 3])
                with col_dt1:
                    del_trib_id = st.number_input("ID a excluir", min_value=1, key="del_trib_id")
                with col_dt2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("❌ Excluir", key="btn_del_trib"):
                        deletar_informe_tributavel(int(del_trib_id))
                        st.success(f"Item #{del_trib_id} excluído.")
                        st.rerun()

        with htab2:
            isento_hist = get_informe_isentos(ano_filtro)
            if not isento_hist:
                st.info("Nenhum rendimento isento gravado para este ano.")
            else:
                df_isento_h = pd.DataFrame([{
                    "ID":            r["id"],
                    "Ano":           r["ano_calendario"],
                    "Fonte":         r["fonte_nome"] or "—",
                    "CNPJ":          r["fonte_cnpj"] or "—",
                    "Código":        r["codigo"] or "—",
                    "Especificação": r["especificacao"] or "—",
                    "Valor (R$)":    r["valor"],
                } for r in isento_hist])
                st.dataframe(df_isento_h, hide_index=True, use_container_width=True)

                st.markdown("---")
                st.markdown("**🗑️ Excluir item isento**")
                col_di1, col_di2 = st.columns([1, 3])
                with col_di1:
                    del_isento_id = st.number_input("ID a excluir", min_value=1, key="del_isento_id")
                with col_di2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("❌ Excluir", key="btn_del_isento"):
                        deletar_informe_isento(int(del_isento_id))
                        st.success(f"Item #{del_isento_id} excluído.")
                        st.rerun()

st.divider()

if not uploaded:
    st.stop()

# ─── Processamento ────────────────────────────────────────────────────────────

with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
    tmp.write(uploaded.read())
    tmp_path = tmp.name

with st.spinner("🔍 Lendo informe e extraindo dados..."):
    dados = ler_informe_rendimentos(tmp_path)
os.unlink(tmp_path)

if dados.get("erro"):
    st.error(f"❌ {dados['erro']}")
    st.stop()

# ─── Identificação ───────────────────────────────────────────────────────────

col_a, col_b, col_c, col_d = st.columns(4)
with col_a:
    st.markdown(f"**👤 Titular:** `{dados.get('titular') or 'Não identificado'}`")
with col_b:
    st.markdown(f"**📄 CPF:** `{dados.get('cpf') or 'Não identificado'}`")
with col_c:
    st.markdown(f"**📅 Ano-Calendário:** `{dados.get('ano_calendario') or 'Não identificado'}`")
with col_d:
    st.markdown(f"**🔍 Parser:** `{dados.get('parser_usado', '?')}`")

with st.expander("🛠️ Debug — Texto bruto do PDF (para novos formatos)"):
    st.text(dados.get("texto_bruto", "")[:5000])

# ─── Fontes Pagadoras ─────────────────────────────────────────────────────────

if dados["fontes_pagadoras"]:
    st.markdown("### 🏦 Fontes Pagadoras")
    for f in dados["fontes_pagadoras"]:
        st.markdown(f"""
        <div class="fonte-card">
            <div>
                <div class="fonte-nome">{f['nome']}</div>
                <div class="fonte-cnpj">CNPJ: {f['cnpj']}</div>
            </div>
            <span class="tag tag-bem">Fonte Pagadora</span>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ─── KPIs ─────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("💸 Rendimentos Tributáveis",
              f"R$ {dados['total_tributavel']:,.2f}".replace(",","X").replace(".",",").replace("X","."))
with c2:
    st.metric("✅ Rendimentos Isentos",
              f"R$ {dados['total_isento']:,.2f}".replace(",","X").replace(".",",").replace("X","."))
with c3:
    total_bens = sum(b["saldo_base"] for b in dados["bens_direitos"])
    st.metric("📁 Total Bens e Direitos",
              f"R$ {total_bens:,.2f}".replace(",","X").replace(".",",").replace("X","."))
with c4:
    n_criptos = len([c for c in dados["criptomoedas"] if c["quantidade"] > 0])
    st.metric("₿ Criptos com saldo", str(n_criptos))

st.markdown("<br>", unsafe_allow_html=True)

# ─── Abas com os dados ────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"💸 Tributáveis ({len(dados['rendimentos_tributaveis'])})",
    f"✅ Isentos ({len(dados['rendimentos_isentos'])})",
    f"📁 Bens e Direitos ({len(dados['bens_direitos'])})",
    f"₿ Criptomoedas ({len(dados['criptomoedas'])})",
    "🔍 Texto Bruto",
])

# ── Tab 1: Rendimentos Tributáveis ────────────────────────────────────────────

with tab1:
    st.markdown("### 💸 Rendimentos Sujeitos à Tributação Exclusiva")
    st.markdown(
        "Esses valores devem ser declarados na ficha "
        "**Rendimentos Sujeitos à Tributação Exclusiva/Definitiva** do IRPF."
    )

    if not dados["rendimentos_tributaveis"]:
        st.info("Nenhum rendimento tributável encontrado neste informe.")
    else:
        for r in dados["rendimentos_tributaveis"]:
            col_desc, col_val = st.columns([4, 1])
            with col_desc:
                st.markdown(
                    f"<span class='tag tag-trib'>Código {r['codigo']}</span> "
                    f"**{r['tipo']}** — {r['especificacao']}",
                    unsafe_allow_html=True
                )
            with col_val:
                st.markdown(
                    f"<div style='text-align:right; font-family:JetBrains Mono; "
                    f"color:#f87171; font-weight:600;'>"
                    f"R$ {r['valor']:,.2f}</div>".replace(",","X").replace(".",",").replace("X","."),
                    unsafe_allow_html=True
                )
            st.markdown("<hr style='border-color:#1e293b; margin:6px 0'>", unsafe_allow_html=True)

        st.markdown(
            f"<div style='text-align:right; font-size:15px; font-weight:700; color:#f1f5f9;'>"
            f"Total: R$ {dados['total_tributavel']:,.2f}</div>".replace(",","X").replace(".",",").replace("X","."),
            unsafe_allow_html=True
        )

    if dados["rendimentos_tributaveis"]:
        st.markdown("---")
        st.markdown("#### 💾 Registrar no App")
        st.markdown("Grava os rendimentos tributáveis no banco para uso no **Auxiliar IRPF**.")

        # Seletor de fonte pagadora (caso haja mais de uma)
        fontes = dados["fontes_pagadoras"]
        fonte_trib = fontes[0] if fontes else {"nome": "", "cnpj": ""}
        if len(fontes) > 1:
            opcoes_trib = [f"{f['nome']} ({f['cnpj']})" for f in fontes]
            sel_trib = st.selectbox("Fonte Pagadora", opcoes_trib, key="sel_fonte_trib")
            fonte_trib = fontes[opcoes_trib.index(sel_trib)]

        if st.button("✅ Gravar Rendimentos Tributáveis", type="primary", key="btn_gravar_trib"):
            sucesso_t = duplicatas_t = 0
            erros_t = []
            for r in dados["rendimentos_tributaveis"]:
                try:
                    inserido = inserir_informe_tributavel(
                        ano_calendario=str(dados.get("ano_calendario", "")),
                        fonte_nome=fonte_trib["nome"],
                        fonte_cnpj=fonte_trib["cnpj"],
                        codigo=r["codigo"],
                        tipo=r["tipo"],
                        especificacao=r["especificacao"],
                        valor=r["valor"],
                    )
                    if inserido:
                        sucesso_t += 1
                    else:
                        duplicatas_t += 1
                except Exception as e:
                    erros_t.append(str(e))

            msgs = []
            if sucesso_t:
                msgs.append(f"🎉 {sucesso_t} rendimento(s) tributável(is) gravado(s)!")
            if duplicatas_t:
                msgs.append(f"⚠️ {duplicatas_t} já existiam e foram ignorado(s).")
            if msgs:
                st.session_state["_informe_sucesso"] = " ".join(msgs)
            if erros_t:
                st.session_state["_informe_erros"] = erros_t
            st.session_state.informe_uploader_key += 1
            st.rerun()

# ── Tab 2: Rendimentos Isentos ────────────────────────────────────────────────

with tab2:
    st.markdown("### ✅ Rendimentos Isentos e Não Tributáveis")
    st.markdown(
        "Esses valores vão na ficha **Rendimentos Isentos e Não Tributáveis** do IRPF. "
        "Inclui LCI, LCA, CRI, CRA, poupança e rendimentos de FII."
    )

    if not dados["rendimentos_isentos"]:
        st.info("Nenhum rendimento isento encontrado neste informe.")
    else:
        for r in dados["rendimentos_isentos"]:
            col_desc, col_val = st.columns([4, 1])
            with col_desc:
                st.markdown(
                    f"<span class='tag tag-isento'>Código {r['codigo']}</span> "
                    f"**{r['especificacao']}**",
                    unsafe_allow_html=True
                )
                st.markdown(
                    f"<span style='font-size:12px; color:#64748b;'>{(r.get('tipo') or '')[:100]}</span>",
                    unsafe_allow_html=True
                )
            with col_val:
                st.markdown(
                    f"<div style='text-align:right; font-family:JetBrains Mono; "
                    f"color:#4ade80; font-weight:600;'>"
                    f"R$ {r['valor']:,.2f}</div>".replace(",","X").replace(".",",").replace("X","."),
                    unsafe_allow_html=True
                )
            st.markdown("<hr style='border-color:#1e293b; margin:6px 0'>", unsafe_allow_html=True)

        st.markdown(
            f"<div style='text-align:right; font-size:15px; font-weight:700; color:#f1f5f9;'>"
            f"Total: R$ {dados['total_isento']:,.2f}</div>".replace(",","X").replace(".",",").replace("X","."),
            unsafe_allow_html=True
        )

    if dados["rendimentos_isentos"]:
        st.markdown("---")
        st.markdown("#### 💾 Registrar no App")
        st.markdown("Grava os rendimentos isentos no banco para uso no **Auxiliar IRPF**.")

        fontes = dados["fontes_pagadoras"]
        fonte_isento = fontes[0] if fontes else {"nome": "", "cnpj": ""}
        if len(fontes) > 1:
            opcoes_isento = [f"{f['nome']} ({f['cnpj']})" for f in fontes]
            sel_isento = st.selectbox("Fonte Pagadora", opcoes_isento, key="sel_fonte_isento")
            fonte_isento = fontes[opcoes_isento.index(sel_isento)]

        if st.button("✅ Gravar Rendimentos Isentos", type="primary", key="btn_gravar_isento"):
            sucesso_i = duplicatas_i = 0
            erros_i = []
            for r in dados["rendimentos_isentos"]:
                try:
                    inserido = inserir_informe_isento(
                        ano_calendario=str(dados.get("ano_calendario", "")),
                        fonte_nome=fonte_isento["nome"],
                        fonte_cnpj=fonte_isento["cnpj"],
                        codigo=r["codigo"],
                        especificacao=r["especificacao"],
                        valor=r["valor"],
                    )
                    if inserido:
                        sucesso_i += 1
                    else:
                        duplicatas_i += 1
                except Exception as e:
                    erros_i.append(str(e))

            msgs = []
            if sucesso_i:
                msgs.append(f"🎉 {sucesso_i} rendimento(s) isento(s) gravado(s)!")
            if duplicatas_i:
                msgs.append(f"⚠️ {duplicatas_i} já existiam e foram ignorado(s).")
            if msgs:
                st.session_state["_informe_sucesso"] = " ".join(msgs)
            if erros_i:
                st.session_state["_informe_erros"] = erros_i
            st.session_state.informe_uploader_key += 1
            st.rerun()

# ── Tab 3: Bens e Direitos ────────────────────────────────────────────────────

with tab3:
    st.markdown("### 📁 Bens e Direitos")
    ano_ant = dados["bens_direitos"][0]["ano_anterior"] if dados["bens_direitos"] else "2024"
    ano_base = dados["bens_direitos"][0]["ano_base"] if dados["bens_direitos"] else "2025"
    st.markdown(
        f"Saldos declarados pelo informe em **31/12/{ano_ant}** e **31/12/{ano_base}**."
    )

    if not dados["bens_direitos"]:
        st.info("Nenhum bem ou direito encontrado neste informe.")
    else:
        df_bens = pd.DataFrame([{
            "Grupo": b["grupo"],
            "Código/Tipo": b["codigo_tipo"],
            "Especificação": b["especificacao"],
            "CNPJ": b["cnpj"] or "—",
            f"Saldo 31/12/{ano_ant}": f"R$ {b['saldo_anterior']:,.2f}".replace(",","X").replace(".",",").replace("X","."),
            f"Saldo 31/12/{ano_base}": f"R$ {b['saldo_base']:,.2f}".replace(",","X").replace(".",",").replace("X","."),
        } for b in dados["bens_direitos"]])

        st.dataframe(df_bens, hide_index=True, use_container_width=True)

        # Botão para registrar renda fixa no app
        st.markdown("---")
        st.markdown("#### 💾 Registrar no App")
        st.markdown(
            "Selecione os itens de **Renda Fixa** para registrar automaticamente no app."
        )

        bens_rf = [
            b for b in dados["bens_direitos"]
            if any(p in b["codigo_tipo"].upper() for p in
                   ["LCI", "LCA", "CDB", "CRI", "CRA", "TÍTULO", "TESOURO",
                    "FUNDO", "POUPAN"])
            and b["saldo_base"] > 0
        ]

        if not bens_rf:
            st.info("Nenhum item de renda fixa identificado para registrar.")
        else:
            for i, b in enumerate(bens_rf):
                with st.expander(
                    f"💾 {b['especificacao']} — "
                    f"R$ {b['saldo_base']:,.2f}".replace(",","X").replace(".",",").replace("X",".")
                ):
                    col1, col2 = st.columns(2)
                    with col1:
                        tipo_rf = st.selectbox(
                            "Tipo", ["LCI", "LCA", "CDB", "CRI", "CRA",
                                     "FUNDO", "TESOURO_SELIC", "OUTRO"],
                            key=f"tipo_rf_{i}"
                        )
                        inst = st.text_input(
                            "Instituição",
                            value=dados["fontes_pagadoras"][0]["nome"]
                            if dados["fontes_pagadoras"] else "",
                            key=f"inst_{i}"
                        )
                    with col2:
                        cnpj_inst = st.text_input(
                            "CNPJ",
                            value=b["cnpj"] or (
                                dados["fontes_pagadoras"][0]["cnpj"]
                                if dados["fontes_pagadoras"] else ""
                            ),
                            key=f"cnpj_inst_{i}"
                        )
                        val_aplic = st.number_input(
                            "Valor Aplicado (R$)",
                            value=b["saldo_anterior"] if b["saldo_anterior"] > 0
                            else b["saldo_base"],
                            format="%.2f",
                            key=f"val_aplic_{i}"
                        )

                    if st.button(f"✅ Registrar", key=f"btn_rf_{i}", type="primary"):
                        try:
                            inserir_renda_fixa(
                                descricao=b["especificacao"],
                                tipo=tipo_rf,
                                instituicao=inst,
                                cnpj_instituicao=cnpj_inst or None,
                                data_aplicacao=f"{ano_ant}-12-31",
                                data_vencimento=None,
                                valor_aplicado=val_aplic,
                                taxa_contratada=None,
                                valor_atual=b["saldo_base"],
                            )
                            st.success(f"✅ {b['especificacao']} registrado!")
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")

# ── Tab 4: Criptomoedas ───────────────────────────────────────────────────────

with tab4:
    st.markdown("### ₿ Criptomoedas")
    st.markdown(
        "Posições de criptoativos conforme reportado pela exchange no informe."
    )

    if not dados["criptomoedas"]:
        st.info("Nenhuma criptomoeda encontrada neste informe.")
    else:
        # Agrupa por ticker mostrando 31/12 do ano base
        criptos_base = [
            c for c in dados["criptomoedas"]
            if str(dados.get("ano_calendario", "2025")) in c["data"]
        ]
        # Se não achou pelo ano, pega todos com quantidade > 0
        if not criptos_base:
            criptos_base = [c for c in dados["criptomoedas"] if c["quantidade"] > 0]

        df_cripto = pd.DataFrame([{
            "Moeda": f"{c['nome']} ({c['ticker']})",
            "Data": c["data"],
            "Quantidade": f"{c['quantidade']:.8f}",
            "Saldo (R$)": f"R$ {c['saldo_reais']:,.2f}".replace(",","X").replace(".",",").replace("X","."),
            "Custo Médio (R$)": f"R$ {c['custo_medio_aquisicao']:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            if c['custo_medio_aquisicao'] > 0 else "—",
        } for c in dados["criptomoedas"]])

        st.dataframe(df_cripto, hide_index=True, use_container_width=True)

        # Registrar criptos com saldo
        st.markdown("---")
        st.markdown("#### 💾 Registrar no App")

        criptos_com_saldo = [c for c in criptos_base if c["quantidade"] > 0]

        if not criptos_com_saldo:
            st.info("Nenhuma criptomoeda com saldo positivo para registrar.")
        else:
            for i, c in enumerate(criptos_com_saldo):
                with st.expander(
                    f"₿ {c['nome']} ({c['ticker']}) — {c['quantidade']:.8f} unidades"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        exchange = st.text_input(
                            "Exchange",
                            value=dados["fontes_pagadoras"][0]["nome"][:30]
                            if dados["fontes_pagadoras"] else "",
                            key=f"exchange_{i}"
                        )
                    with col2:
                        qtd_c = st.number_input(
                            "Quantidade",
                            value=c["quantidade"],
                            format="%.8f",
                            key=f"qtd_c_{i}"
                        )
                    with col3:
                        preco_c = st.number_input(
                            "Custo Médio (R$/unidade)",
                            value=c["custo_medio_aquisicao"]
                            if c["custo_medio_aquisicao"] > 0 else 0.01,
                            format="%.2f",
                            key=f"preco_c_{i}"
                        )

                    if st.button(f"✅ Registrar {c['ticker']}", key=f"btn_c_{i}", type="primary"):
                        try:
                            inserir_cripto(
                                moeda=c["ticker"],
                                tipo_operacao="COMPRA",
                                data_operacao=f"{ano_base}-12-31",
                                quantidade=qtd_c,
                                preco_unitario_brl=preco_c,
                                exchange=exchange or None,
                                taxa=0.0,
                            )
                            st.success(f"✅ {c['ticker']} registrado!")
                        except Exception as e:
                            st.error(f"❌ Erro: {e}")

# ── Tab 5: Texto bruto ────────────────────────────────────────────────────────

with tab5:
    st.markdown("### 🔍 Texto Extraído do PDF")
    st.markdown(
        "Use isso para conferir se a extração foi correta ou para localizar "
        "dados que não foram reconhecidos automaticamente."
    )
    st.text_area(
        "Conteúdo bruto",
        value=dados["texto_bruto"],
        height=500,
        disabled=True
    )

# ─── Rodapé ───────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#374151; font-size:0.75rem;'>"
    "📋 Informe de Rendimentos · Os dados são extraídos automaticamente do PDF "
    "e devem ser conferidos antes de uso na declaração."
    "</p>",
    unsafe_allow_html=True
)
