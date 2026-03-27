"""
📊 Cotações e Análise
Mostra cotações em tempo real e análise de performance.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from database.db import init_db, get_carteira_completa, get_todos_ativos
from modules.cotacoes import get_historico, calcular_variacao

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
</style>
""", unsafe_allow_html=True)

st.markdown("# 📊 Cotações e Análise")
st.divider()

ativos = get_todos_ativos()
carteira = get_carteira_completa()

if not ativos:
    st.info("📂 Nenhum ativo cadastrado ainda.")
    st.stop()

tickers = [a["ticker"] for a in ativos if a["tipo"] not in ("RENDA_FIXA", "CRIPTO")]

# ─── Seletor de ativo ────────────────────────────────────────────────────────

col1, col2 = st.columns([2, 1])
with col1:
    ticker_sel = st.selectbox("Selecione o ativo", tickers)
with col2:
    periodo = st.selectbox("Período", ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                           index=3, format_func=lambda x: {
                               "1mo": "1 mês", "3mo": "3 meses", "6mo": "6 meses",
                               "1y": "1 ano", "2y": "2 anos", "5y": "5 anos"
                           }[x])

# ─── Variações ────────────────────────────────────────────────────────────────

with st.spinner(f"Carregando dados de {ticker_sel}..."):
    variacao = calcular_variacao(ticker_sel)
    historico = get_historico(ticker_sel, periodo)

if variacao["preco_atual"]:
    c1, c2, c3, c4, c5 = st.columns(5)
    preco = variacao["preco_atual"]

    posicao = next((p for p in carteira if p["ticker"] == ticker_sel), None)

    with c1:
        st.metric("Preço Atual", f"R$ {preco:.2f}")
    with c2:
        vd = variacao["var_dia"]
        st.metric("No dia", f"{vd:+.2f}%" if vd else "—",
                  delta=f"{vd:+.2f}%" if vd else None)
    with c3:
        vm = variacao["var_mes"]
        st.metric("No mês", f"{vm:+.2f}%" if vm else "—")
    with c4:
        va = variacao["var_ano"]
        st.metric("No ano", f"{va:+.2f}%" if va else "—")
    with c5:
        if posicao:
            pm = posicao["preco_medio"]
            rent_pm = (preco - pm) / pm * 100 if pm > 0 else 0
            st.metric("vs Preço Médio",
                      f"R$ {pm:.2f}",
                      delta=f"{rent_pm:+.2f}%")
        else:
            st.metric("Na carteira", "Não")
else:
    st.warning(f"⚠️ Não foi possível obter cotação de {ticker_sel}. Verifique o ticker.")

# ─── Gráfico histórico ────────────────────────────────────────────────────────

if historico is not None and not historico.empty:
    st.markdown(f"#### 📉 Histórico de Preços — {ticker_sel}")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=historico.index,
        open=historico["Open"],
        high=historico["High"],
        low=historico["Low"],
        close=historico["Close"],
        name=ticker_sel,
        increasing_line_color="#4ade80",
        decreasing_line_color="#f87171",
    ))

    # Linha de preço médio se tiver na carteira
    if posicao and posicao["preco_medio"] > 0:
        fig.add_hline(
            y=posicao["preco_medio"],
            line_dash="dash",
            line_color="#fbbf24",
            annotation_text=f"PM: R$ {posicao['preco_medio']:.2f}",
            annotation_position="top right",
        )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#111827",
        xaxis=dict(gridcolor="#1f2937", color="#94a3b8"),
        yaxis=dict(gridcolor="#1f2937", color="#94a3b8", tickprefix="R$ "),
        height=450,
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis_rangeslider_visible=False,
        legend=dict(font=dict(color="white")),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Volume
    fig_vol = go.Figure(go.Bar(
        x=historico.index,
        y=historico["Volume"],
        marker_color="#3b82f6",
        opacity=0.7,
        name="Volume"
    ))
    fig_vol.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#111827",
        xaxis=dict(gridcolor="#1f2937", color="#94a3b8"),
        yaxis=dict(gridcolor="#1f2937", color="#94a3b8"),
        height=150,
        margin=dict(t=5, b=5, l=10, r=10),
        showlegend=False,
    )
    st.plotly_chart(fig_vol, use_container_width=True)
else:
    st.info("Dados históricos não disponíveis para este ativo.")

# ─── Dados da posição ─────────────────────────────────────────────────────────

if posicao:
    st.markdown("#### 💼 Sua Posição")
    preco_at = variacao["preco_atual"] or posicao["preco_medio"]
    valor_atual = posicao["quantidade"] * preco_at
    ganho = valor_atual - posicao["custo_total"]
    rent = ganho / posicao["custo_total"] * 100 if posicao["custo_total"] > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Quantidade", f"{posicao['quantidade']:.0f} cotas")
    with c2:
        st.metric("Preço Médio", f"R$ {posicao['preco_medio']:.4f}")
    with c3:
        st.metric("Custo Total", f"R$ {posicao['custo_total']:.2f}")
    with c4:
        st.metric("Valor Atual", f"R$ {valor_atual:.2f}",
                  delta=f"R$ {ganho:+.2f} ({rent:+.2f}%)")
