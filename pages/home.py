"""
💼 Patrimônio — Dashboard principal
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from database.db import get_carteira_completa, get_rendimentos, get_renda_fixa, get_cripto_posicao, get_stats_envios
from modules.cotacoes import get_cotacoes_lote

col_titulo, col_refresh = st.columns([5, 1])
with col_titulo:
    st.markdown("# 💼 Patrimônio")
    st.markdown("<p style='color:#64748b; margin-top:-10px;'>Controle de investimentos e auxiliar IRPF</p>", unsafe_allow_html=True)
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

@st.cache_data(ttl=300)
def carregar_dados():
    carteira    = get_carteira_completa()
    renda_fixa  = get_renda_fixa()
    cripto      = get_cripto_posicao()
    rendimentos = get_rendimentos()
    tickers_b3  = [p["ticker"] for p in carteira]
    cotacoes    = get_cotacoes_lote(tickers_b3) if tickers_b3 else {}
    return carteira, renda_fixa, cripto, rendimentos, cotacoes

try:
    carteira, renda_fixa, cripto, rendimentos, cotacoes = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    carteira, renda_fixa, cripto, rendimentos, cotacoes = [], [], [], [], {}

def calc_valor_atual(posicao):
    cotacao = cotacoes.get(posicao["ticker"])
    return posicao["quantidade"] * cotacao if cotacao else posicao["custo_total"]

def calc_rentabilidade(posicao):
    va = calc_valor_atual(posicao)
    return (va - posicao["custo_total"]) / posicao["custo_total"] * 100 if posicao["custo_total"] > 0 else 0.0

total_b3          = sum(calc_valor_atual(p) for p in carteira) if carteira else 0
total_rf          = sum(rf["valor_atual"] or rf["valor_aplicado"] for rf in renda_fixa) if renda_fixa else 0
total_cripto      = sum(c["quantidade"] * (cotacoes.get(c["moeda"]) or c["preco_medio"]) for c in cripto) if cripto else 0
total_rendimentos = sum(r["valor_total"] for r in rendimentos) if rendimentos else 0
total_geral       = total_b3 + total_rf + total_cripto
total_investido_b3 = sum(p["custo_total"] for p in carteira)
ganho_total        = total_b3 - total_investido_b3

# ── KPIs ─────────────────────────────────────────────────────────────────────

st.markdown("### 📊 Visão Geral")
col1, col2, col3, col4, col5 = st.columns(5)

def fmt(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with col1: st.metric("💰 Patrimônio Total",    fmt(total_geral))
with col2: st.metric("📈 Renda Variável",       fmt(total_b3),
                      delta=f"R$ {ganho_total:+,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if ganho_total else None)
with col3: st.metric("🏦 Renda Fixa",           fmt(total_rf))
with col4: st.metric("₿ Cripto",                fmt(total_cripto))
with col5: st.metric("💵 Rendimentos Recebidos", fmt(total_rendimentos))

st.markdown("<br>", unsafe_allow_html=True)

# ── Gráficos ─────────────────────────────────────────────────────────────────

if total_geral > 0:
    col_grafico1, col_grafico2 = st.columns([1, 2])

    with col_grafico1:
        st.markdown("#### 🥧 Alocação por Classe")
        labels, values, colors = [], [], []
        if total_b3 > 0:
            tipo_totais = {}
            for p in carteira:
                tipo = p.get("tipo", "ACAO")
                tipo_totais[tipo] = tipo_totais.get(tipo, 0) + calc_valor_atual(p)
            cores_map = {"FII": "#3b82f6", "FIAGRO": "#22c55e", "ACAO": "#a855f7"}
            for tipo, valor in tipo_totais.items():
                labels.append(tipo); values.append(valor); colors.append(cores_map.get(tipo, "#64748b"))
        if total_rf > 0:
            labels.append("Renda Fixa"); values.append(total_rf); colors.append("#818cf8")
        if total_cripto > 0:
            labels.append("Cripto"); values.append(total_cripto); colors.append("#f97316")

        fig_pie = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=0.55, marker_colors=colors,
            textinfo="percent", textfont=dict(size=13, color="white"),
            hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
        )])
        fig_pie.add_annotation(
            text=f"R$ {total_geral:,.0f}".replace(",", "."),
            x=0.5, y=0.5, font=dict(size=13, color="white", family="JetBrains Mono"), showarrow=False
        )
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True, legend=dict(font=dict(color="white", size=11)),
            margin=dict(t=0, b=0, l=0, r=0), height=280,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_grafico2:
        st.markdown("#### 📋 Carteira de Renda Variável")
        if carteira:
            dados_tabela = []
            for p in carteira:
                va   = calc_valor_atual(p)
                rent = calc_rentabilidade(p)
                cotacao = cotacoes.get(p["ticker"], "—")
                dados_tabela.append({
                    "Ticker": p["ticker"], "Tipo": p.get("tipo", "—"), "Qtd": p["quantidade"],
                    "PM (R$)": f"{p['preco_medio']:.2f}",
                    "Cotação (R$)": f"{cotacao:.2f}" if isinstance(cotacao, float) else "—",
                    "Custo (R$)": f"{p['custo_total']:.2f}",
                    "Valor Atual (R$)": f"{va:.2f}",
                    "Rent. (%)": f"{rent:+.2f}%",
                })
            st.dataframe(pd.DataFrame(dados_tabela), hide_index=True, use_container_width=True, height=300)
        else:
            st.info("📂 Nenhum ativo cadastrado. Use o menu lateral para adicionar.")
else:
    st.info("👋 Bem-vindo! Use o menu lateral para começar a registrar seus investimentos.")

# ── Renda Fixa ───────────────────────────────────────────────────────────────

if renda_fixa:
    st.markdown("### 🏦 Renda Fixa")
    dados_rf = [{
        "Descrição": rf["descricao"], "Tipo": rf["tipo"], "Instituição": rf["instituicao"],
        "Aplicado (R$)": f"{rf['valor_aplicado']:.2f}",
        "Atual (R$)": f"{rf['valor_atual'] or rf['valor_aplicado']:.2f}",
        "Rendimento (R$)": f"{(rf['valor_atual'] or rf['valor_aplicado']) - rf['valor_aplicado']:+.2f}",
        "Vencimento": rf.get("data_vencimento", "—"),
        "Taxa": rf.get("taxa_contratada", "—"),
    } for rf in renda_fixa]
    st.dataframe(pd.DataFrame(dados_rf), hide_index=True, use_container_width=True)

# ── Últimos rendimentos ───────────────────────────────────────────────────────

if rendimentos:
    st.markdown("### 💵 Últimos Rendimentos")
    ultimos = sorted(rendimentos, key=lambda r: r["data_pagamento"], reverse=True)[:10]
    st.dataframe(pd.DataFrame([{
        "Ticker": r["ticker"], "Data": r["data_pagamento"],
        "Valor/Cota (R$)": f"{r['valor_por_cota']:.4f}", "Cotas": r["quantidade_cotas"],
        "Total (R$)": f"{r['valor_total']:.2f}",
        "Isento IR": "✅" if r.get("isento_ir", 1) else "❌",
    } for r in ultimos]), hide_index=True, use_container_width=True)

st.markdown("---")

# ── Contador de cópias enviadas ───────────────────────────────────────────────
stats = get_stats_envios()
if stats["total"] > 0:
    ultima_fmt = ""
    if stats["ultima"]:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(stats["ultima"])
            ultima_fmt = f" · última em {dt.strftime('%d/%m/%Y às %H:%M')}"
        except Exception:
            pass
    st.markdown(
        f"<p style='text-align:center; color:#374151; font-size:0.75rem;'>"
        f"📦 <strong style='color:#64748b'>{stats['total']}</strong> cópias do app enviadas{ultima_fmt}"
        f"</p>",
        unsafe_allow_html=True
    )

st.markdown(
    "<p style='text-align:center; color:#374151; font-size:0.75rem;'>"
    "💼 App de Patrimônio · Cotações via Yahoo Finance · Dados armazenados localmente</p>",
    unsafe_allow_html=True
)
