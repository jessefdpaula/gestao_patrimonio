"""
🧾 Auxiliar IRPF
Gera os dados prontos para preencher a declaração do Imposto de Renda.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

from database.db import init_db, marcar_declarado, desmarcar_declarado, get_declarados, get_declarados_progresso
from modules.ir_helper import gerar_relatorio_ir, gerar_rendimentos_tributaveis_informe, gerar_rendimentos_isentos_informe

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #0d1117; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f1117 0%, #1a1f2e 100%); border-right: 1px solid #2d3748; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
h1, h2, h3 { color: #f1f5f9 !important; }
p, li, div { color: #cbd5e1; }
.stButton > button { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white !important; border: none; border-radius: 8px; font-weight: 500; }
.stTabs [data-baseweb="tab-list"] { background: #1a1f2e; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #94a3b8 !important; }
.stTabs [aria-selected="true"] { background: #3b82f6 !important; color: white !important; }
.info-card { background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px; padding: 16px; margin-bottom: 8px; }
.discriminacao { background: #0f1117; border: 1px solid #374151; border-radius: 6px; padding: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #94a3b8; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 🧾 Auxiliar IRPF")
st.markdown("Dados organizados para preencher sua declaração do Imposto de Renda.")
st.divider()

# ─── Seletor de ano ───────────────────────────────────────────────────────────

ano_atual = datetime.today().year
col_ano, col_btn = st.columns([1, 4])
with col_ano:
    ano_base = st.selectbox(
        "Ano-base",
        list(range(ano_atual - 1, ano_atual - 6, -1)),
        index=0,
        help="Ano dos rendimentos (declaração entregue no ano seguinte)"
    )

with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    gerar = st.button("🔄 Gerar Dados IRPF", type="primary")

if gerar or True:  # Carrega automaticamente
    with st.spinner("Calculando dados..."):
        relatorio = gerar_relatorio_ir(ano_base)

    bens = relatorio["bens_e_direitos"]
    rendimentos_isentos = relatorio["rendimentos_isentos"]
    ganho_capital = relatorio["ganho_capital"]
    tributaveis_informe = relatorio["rendimentos_tributaveis_informe"]
    isentos_informe = relatorio["rendimentos_isentos_informe"]

    # ── Progresso geral ───────────────────────────────────────────────────────
    decl_bens       = get_declarados(ano_base, "bens")
    decl_rend_fii   = get_declarados(ano_base, "rend_fii")
    decl_trib       = get_declarados(ano_base, "trib_informe")
    decl_isento_inf = get_declarados(ano_base, "isento_informe")
    decl_gc         = get_declarados(ano_base, "ganho_capital")

    total_itens = len(bens) + len(rendimentos_isentos) + len(tributaveis_informe) + len(isentos_informe) + len(ganho_capital)
    total_decl  = len(decl_bens) + len(decl_rend_fii) + len(decl_trib) + len(decl_isento_inf) + len(decl_gc)

    if total_itens > 0:
        pct = int(total_decl / total_itens * 100)
        st.progress(pct / 100, text=f"**Progresso da declaração:** {total_decl}/{total_itens} itens declarados ({pct}%)")
    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"🏠 Bens e Direitos ({len(decl_bens)}/{len(bens)})",
        f"💵 Rendimentos Isentos FII/FIAGRO ({len(decl_rend_fii)}/{len(rendimentos_isentos)})",
        f"💸 Tributáveis — Informe ({len(decl_trib)}/{len(tributaveis_informe)})",
        f"✅ Isentos — Informe ({len(decl_isento_inf)}/{len(isentos_informe)})",
        f"📈 Ganho de Capital ({len(decl_gc)}/{len(ganho_capital)})",
    ])

    # ─── Bens e Direitos ──────────────────────────────────────────────────────

    with tab1:
        st.markdown(f"### 🏠 Bens e Direitos — Ano-base {ano_base}")
        st.markdown(
            "Estes dados devem ser lançados na ficha **Bens e Direitos** do programa IRPF."
        )

        if not bens:
            st.info("📂 Nenhum bem cadastrado. Adicione seus ativos no Lançamento Manual.")
        else:
            # Exportar como CSV
            df_bens = pd.DataFrame([{
                "Grupo": b["grupo"],
                "Código": b["codigo"],
                "Ticker/ID": b["ticker"],
                "Nome": b["nome"],
                "CNPJ Fundo": b["cnpj_fundo"],
                "Localização": b["localizacao"],
                "Discriminação": b["discriminacao"],
                f"Valor 31/12/{ano_base-1} (R$)": b["valor_ano_anterior"],
                f"Valor 31/12/{ano_base} (R$)": b["valor_ano_base"],
            } for b in bens])

            col_dl, _ = st.columns([1, 4])
            with col_dl:
                csv = df_bens.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
                st.download_button(
                    "⬇️ Baixar CSV",
                    data=csv,
                    file_name=f"bens_direitos_{ano_base}.csv",
                    mime="text/csv",
                )

            # Exibição por bem
            for b in bens:
                ref_bem = f"{b['grupo']}_{b['codigo']}_{b['ticker']}"
                is_decl = ref_bem in decl_bens
                icone = "✅" if is_decl else "⬜"

                with st.expander(
                    f"{icone} **{b['ticker']}** — Grupo {b['grupo']}, Código {b['codigo']} — "
                    f"{b['descricao_codigo']}"
                ):
                    novo = st.checkbox(
                        "Declarado no IRPF",
                        value=is_decl,
                        key=f"decl_bens_{ref_bem}_{ano_base}"
                    )
                    if novo != is_decl:
                        if novo:
                            marcar_declarado(ano_base, "bens", ref_bem)
                        else:
                            desmarcar_declarado(ano_base, "bens", ref_bem)
                        st.rerun()

                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**Grupo:** `{b['grupo']}`")
                        st.markdown(f"**Código:** `{b['codigo']}`")
                        st.markdown(f"**Localização:** `{b['localizacao']}`")
                    with c2:
                        val_ant = b['valor_ano_anterior']
                        val_base = b['valor_ano_base']
                        variacao = val_base - val_ant
                        st.markdown(f"**31/12/{ano_base-1}:** R$ `{val_ant:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                        st.markdown(f"**31/12/{ano_base}:** R$ `{val_base:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                        if variacao != 0:
                            cor = "🟢" if variacao > 0 else "🔴"
                            st.markdown(f"**Variação:** {cor} R$ `{variacao:+,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                    with c3:
                        if b.get("cnpj_fundo"):
                            st.markdown(f"**CNPJ Fundo:** `{b['cnpj_fundo']}`")

                    st.markdown("**Discriminação sugerida:**")
                    st.markdown(
                        f"<div class='discriminacao'>{b['discriminacao']}</div>",
                        unsafe_allow_html=True
                    )
                    col_copy, _ = st.columns([1, 5])

    # ─── Rendimentos Isentos FII/FIAGRO ──────────────────────────────────────

    with tab2:
        st.markdown(f"### 💵 Rendimentos Isentos e Não Tributáveis — {ano_base}")
        st.markdown(
            "Rendimentos de FIIs e FIAGROs para Pessoa Física são **isentos de IR** "
            "(art. 3º, §3º, Lei 11.033/2004). Lançar na ficha **Rendimentos Isentos e "
            "Não Tributáveis**, código **26 - Outros**."
        )

        if not rendimentos_isentos:
            st.info("📂 Nenhum rendimento registrado para este período.")
        else:
            total_isento = sum(r["total_recebido"] for r in rendimentos_isentos)
            st.success(f"💰 Total de rendimentos isentos em {ano_base}: **R$ {total_isento:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))

            for r in rendimentos_isentos:
                ref_rfi = r["ticker"]
                is_decl_rfi = ref_rfi in decl_rend_fii
                icone_rfi = "✅" if is_decl_rfi else "⬜"

                with st.expander(
                    f"{icone_rfi} **{r['ticker']}** — {r['nome'] or r['ticker']} — "
                    f"R$ {r['total_recebido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ):
                    novo_rfi = st.checkbox(
                        "Declarado no IRPF",
                        value=is_decl_rfi,
                        key=f"decl_rfi_{ref_rfi}_{ano_base}"
                    )
                    if novo_rfi != is_decl_rfi:
                        if novo_rfi:
                            marcar_declarado(ano_base, "rend_fii", ref_rfi)
                        else:
                            desmarcar_declarado(ano_base, "rend_fii", ref_rfi)
                        st.rerun()
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"**CNPJ Fonte:** `{r['cnpj_fonte'] or '—'}`")
                    with c2:
                        st.markdown(f"**Código Ficha:** `{r['codigo_ficha']}`")
                    with c3:
                        st.markdown(f"**Total:** R$ `{r['total_recebido']:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))

            df_rend = pd.DataFrame([{
                "Ticker": r["ticker"],
                "Nome": r["nome"],
                "CNPJ Fonte Pagadora": r["cnpj_fonte"],
                "Tipo": r["tipo"],
                "Código Ficha": r["codigo_ficha"],
                "Total Recebido (R$)": r["total_recebido"],
            } for r in rendimentos_isentos])

            csv_rend = df_rend.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button(
                "⬇️ Baixar CSV",
                data=csv_rend,
                file_name=f"rendimentos_isentos_{ano_base}.csv",
                mime="text/csv",
            )

    # ─── Rendimentos Tributáveis — Informes ───────────────────────────────────

    with tab3:
        st.markdown(f"### 💸 Rendimentos Tributáveis — Informes de Rendimentos — {ano_base}")
        st.markdown(
            "Valores importados de informes de rendimentos (PDFs). "
            "Declarar na ficha **Rendimentos Sujeitos à Tributação Exclusiva/Definitiva** do IRPF."
        )

        if not tributaveis_informe:
            st.info("📂 Nenhum rendimento tributável importado de informes para este ano. "
                    "Importe um PDF na página **Informes de Rendimentos**.")
        else:
            total_trib = sum(f["total"] for f in tributaveis_informe)
            st.success(
                f"💸 Total de rendimentos tributáveis em {ano_base}: "
                f"**R$ {total_trib:,.2f}**".replace(",", "X").replace(".", ",").replace("X", ".")
            )

            for fonte in tributaveis_informe:
                ref_trib = fonte["fonte_cnpj"] or fonte["fonte_nome"]
                is_decl_trib = ref_trib in decl_trib
                icone_trib = "✅" if is_decl_trib else "⬜"

                with st.expander(
                    f"{icone_trib} 🏦 **{fonte['fonte_nome']}** — "
                    f"CNPJ: {fonte['fonte_cnpj'] or '—'} — "
                    f"Total: R$ {fonte['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ):
                    novo_trib = st.checkbox(
                        "Declarado no IRPF",
                        value=is_decl_trib,
                        key=f"decl_trib_{ref_trib}_{ano_base}"
                    )
                    if novo_trib != is_decl_trib:
                        if novo_trib:
                            marcar_declarado(ano_base, "trib_informe", ref_trib)
                        else:
                            desmarcar_declarado(ano_base, "trib_informe", ref_trib)
                        st.rerun()
                    st.markdown("---")
                    df_trib = pd.DataFrame([{
                        "Código": item["codigo"],
                        "Tipo": item["tipo"],
                        "Especificação": item["especificacao"],
                        "Valor (R$)": item["valor"],
                    } for item in fonte["itens"]])
                    st.dataframe(df_trib, hide_index=True, use_container_width=True)

            # Exportar como CSV
            rows_csv = []
            for fonte in tributaveis_informe:
                for item in fonte["itens"]:
                    rows_csv.append({
                        "Fonte Pagadora": fonte["fonte_nome"],
                        "CNPJ Fonte": fonte["fonte_cnpj"],
                        "Código": item["codigo"],
                        "Tipo": item["tipo"],
                        "Especificação": item["especificacao"],
                        "Valor (R$)": item["valor"],
                    })
            df_trib_all = pd.DataFrame(rows_csv)
            col_dl, _ = st.columns([1, 4])
            with col_dl:
                csv_trib = df_trib_all.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
                st.download_button(
                    "⬇️ Baixar CSV",
                    data=csv_trib,
                    file_name=f"tributaveis_informe_{ano_base}.csv",
                    mime="text/csv",
                )

    # ─── Rendimentos Isentos — Informes ──────────────────────────────────────

    with tab4:
        st.markdown(f"### ✅ Rendimentos Isentos — Informes de Rendimentos — {ano_base}")
        st.markdown(
            "Valores importados de informes de rendimentos (PDFs). "
            "Declarar na ficha **Rendimentos Isentos e Não Tributáveis** do IRPF."
        )

        if not isentos_informe:
            st.info("📂 Nenhum rendimento isento importado de informes para este ano. "
                    "Importe um PDF na página **Informes de Rendimentos**.")
        else:
            total_isento_inf = sum(f["total"] for f in isentos_informe)
            st.success(
                f"✅ Total de rendimentos isentos (informe) em {ano_base}: "
                f"**R$ {total_isento_inf:,.2f}**".replace(",", "X").replace(".", ",").replace("X", ".")
            )

            for fonte in isentos_informe:
                ref_isento_i = fonte["fonte_cnpj"] or fonte["fonte_nome"]
                is_decl_ii = ref_isento_i in decl_isento_inf
                icone_ii = "✅" if is_decl_ii else "⬜"

                with st.expander(
                    f"{icone_ii} 🏦 **{fonte['fonte_nome']}** — "
                    f"CNPJ: {fonte['fonte_cnpj'] or '—'} — "
                    f"Total: R$ {fonte['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                ):
                    novo_ii = st.checkbox(
                        "Declarado no IRPF",
                        value=is_decl_ii,
                        key=f"decl_isento_inf_{ref_isento_i}_{ano_base}"
                    )
                    if novo_ii != is_decl_ii:
                        if novo_ii:
                            marcar_declarado(ano_base, "isento_informe", ref_isento_i)
                        else:
                            desmarcar_declarado(ano_base, "isento_informe", ref_isento_i)
                        st.rerun()
                    st.markdown("---")
                    df_isento_inf = pd.DataFrame([{
                        "Código": item["codigo"],
                        "Especificação": item["especificacao"],
                        "Valor (R$)": item["valor"],
                    } for item in fonte["itens"]])
                    st.dataframe(df_isento_inf, hide_index=True, use_container_width=True)

            rows_isento_csv = []
            for fonte in isentos_informe:
                for item in fonte["itens"]:
                    rows_isento_csv.append({
                        "Fonte Pagadora": fonte["fonte_nome"],
                        "CNPJ Fonte": fonte["fonte_cnpj"],
                        "Código": item["codigo"],
                        "Especificação": item["especificacao"],
                        "Valor (R$)": item["valor"],
                    })
            df_isento_all = pd.DataFrame(rows_isento_csv)
            col_dl2, _ = st.columns([1, 4])
            with col_dl2:
                csv_isento = df_isento_all.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
                st.download_button(
                    "⬇️ Baixar CSV",
                    data=csv_isento,
                    file_name=f"isentos_informe_{ano_base}.csv",
                    mime="text/csv",
                )

    # ─── Ganho de Capital ─────────────────────────────────────────────────────

    with tab5:
        st.markdown(f"### 📈 Ganho de Capital — {ano_base}")
        st.markdown(
            "Vendas realizadas no ano. "
            "**FIIs:** alíquota de 20%. "
            "**Ações:** isentos até R$20k/mês, 15% acima. "
            "**FIAGROs:** 15%."
        )

        if not ganho_capital:
            st.info("📂 Nenhuma venda registrada neste período.")
        else:
            total_ir = sum(g["ir_devido"] for g in ganho_capital)
            total_ganho = sum(g["ganho_liquido"] for g in ganho_capital)

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric("Ganho líquido total", f"R$ {total_ganho:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col_m2:
                st.metric("IR devido total", f"R$ {total_ir:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                          delta="Verificar DARF" if total_ir > 0 else "Nada a pagar")

            for i, g in enumerate(ganho_capital):
                ref_gc = f"{g['mes']}_{g['ticker']}_{i}"
                is_decl_gc = ref_gc in decl_gc
                icone_gc = "✅" if is_decl_gc else "⬜"
                darf_info = f" — DARF R$ {g['ir_devido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if g["ir_devido"] > 0 else " — Isento"

                with st.expander(
                    f"{icone_gc} **{g['mes']} · {g['ticker']}** — "
                    f"Ganho R$ {g['ganho_liquido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + darf_info
                ):
                    novo_gc = st.checkbox(
                        "DARF pago / declarado no GCAP",
                        value=is_decl_gc,
                        key=f"decl_gc_{ref_gc}_{ano_base}"
                    )
                    if novo_gc != is_decl_gc:
                        if novo_gc:
                            marcar_declarado(ano_base, "ganho_capital", ref_gc)
                        else:
                            desmarcar_declarado(ano_base, "ganho_capital", ref_gc)
                        st.rerun()
                    st.markdown("---")
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown(f"**Qtd vendida:** `{g['quantidade_vendida']}`")
                        st.markdown(f"**Valor venda:** R$ `{g['valor_venda']:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                    with c2:
                        st.markdown(f"**Custo aquisição:** R$ `{g['custo_aquisicao']:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                        st.markdown(f"**Ganho líquido:** R$ `{g['ganho_liquido']:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                    with c3:
                        st.markdown(f"**Alíquota:** `{g['aliquota_pct']:.0f}%`")
                        st.markdown(f"**IR devido:** R$ `{g['ir_devido']:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))
                    with c4:
                        st.markdown(f"**Isento:** {'✅ Sim' if g['isento'] else '❌ Não'}")
                        if g["total_vendas_acoes_mes"]:
                            st.markdown(f"**Total vendas ações no mês:** R$ `{g['total_vendas_acoes_mes']:,.2f}`".replace(",", "X").replace(".", ",").replace("X", "."))

            df_gc = pd.DataFrame([{
                "Mês": g["mes"],
                "Ticker": g["ticker"],
                "Tipo": g["tipo"],
                "Qtd Vendida": g["quantidade_vendida"],
                "Valor Venda (R$)": g["valor_venda"],
                "Custo Aquis. (R$)": g["custo_aquisicao"],
                "Ganho Líquido (R$)": g["ganho_liquido"],
                "Isento": "✅" if g["isento"] else "❌",
                "Alíquota": f"{g['aliquota_pct']:.0f}%",
                "IR Devido (R$)": g["ir_devido"],
            } for g in ganho_capital])

            st.dataframe(df_gc, hide_index=True, use_container_width=True)

            if total_ir > 0:
                st.warning(
                    f"⚠️ Total de R$ {total_ir:.2f} em DARF a pagar. "
                    "Verifique o prazo no programa GCAP da Receita Federal "
                    "(vencimento no último dia útil do mês seguinte à venda)."
                )

            csv_gc = df_gc.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button(
                "⬇️ Baixar CSV",
                data=csv_gc,
                file_name=f"ganho_capital_{ano_base}.csv",
                mime="text/csv",
            )

    # ─── Dicas gerais ─────────────────────────────────────────────────────────

    with st.expander("💡 Dicas para o IRPF"):
        st.markdown("""
**FIIs e FIAGROs — Bens e Direitos:**
- Grupo `07`, Código `03` (FII) ou `02` (FIAGRO)
- O valor declarado é o **custo de aquisição** (preço médio × quantidade), não o valor de mercado.
- Informe o CNPJ do fundo e a corretora na discriminação.

**FIIs e FIAGROs — Rendimentos:**
- Ficha: **Rendimentos Isentos e Não Tributáveis**
- Código: **26 - Outros**
- Fonte pagadora: nome e CNPJ do fundo.

**Ações — Ganho de Capital:**
- Vendas ≤ R$20.000/mês: **isentas**
- Vendas > R$20.000/mês: **15% sobre o lucro** (swing trade) ou **20%** (day trade)
- O pagamento é via **DARF** (código 6015) até o último dia útil do mês seguinte.

**FIIs — Ganho de Capital:**
- Sempre tributados em **20%** sobre o lucro, independente do valor vendido.
- DARF código **6015**.

**Cripto:**
- Obrigatório declarar se o valor total de criptos superar **R$5.000**.
- Ganhos em vendas > R$35.000/mês: **15% a 22,5%** de IR.
""")
