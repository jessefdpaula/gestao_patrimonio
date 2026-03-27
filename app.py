"""
💼 App de Controle de Patrimônio — Ponto de entrada e navegação.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import re
import streamlit as st
from database.db import init_db, registrar_envio_app
from modules.email_sender import enviar_copia

st.set_page_config(
    page_title="Patrimônio",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS global ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #0d1117; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1117 0%, #1a1f2e 100%);
    border-right: 1px solid #2d3748;
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

/* Oculta a navegação automática do Streamlit */
[data-testid="stSidebarNav"] { display: none !important; }

/* Botões de navegação lateral */
[data-testid="stPageLink"] {
    margin-bottom: 4px;
}
[data-testid="stPageLink"] a {
    display: flex !important;
    align-items: center;
    background: #1e2535 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    color: #cbd5e1 !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    text-decoration: none !important;
    transition: all 0.18s ease !important;
    width: 100%;
}
[data-testid="stPageLink"] a:hover {
    background: #2d3a52 !important;
    border-color: #3b82f6 !important;
    color: #f1f5f9 !important;
}
[data-testid="stPageLink"] a[aria-current="page"] {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    border-color: #3b82f6 !important;
    color: #ffffff !important;
}

/* Métricas, títulos, frames, botões, tabs, expanders */
h1, h2, h3 { color: #f1f5f9 !important; font-family: 'Space Grotesk', sans-serif !important; }
h1 { font-weight: 700 !important; }
h2 { font-weight: 600 !important; font-size: 1.2rem !important; }
p, li, span, div { color: #cbd5e1; }
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%);
    border: 1px solid #2d3748; border-radius: 12px; padding: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
[data-testid="metric-container"] label { color: #94a3b8 !important; font-size: 0.75rem !important; font-weight: 500 !important; text-transform: uppercase !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 1.6rem !important; font-weight: 700 !important; font-family: 'JetBrains Mono', monospace !important; }
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
.stButton > button { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white !important; border: none; border-radius: 8px; font-weight: 500; transition: all 0.2s; }
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(59,130,246,0.4); }
.stTabs [data-baseweb="tab-list"] { background: #1a1f2e; border-radius: 8px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #94a3b8 !important; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #3b82f6 !important; color: white !important; }
.streamlit-expanderHeader { background: #1a1f2e !important; border-radius: 8px !important; color: #f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)

init_db()

# ─── Dialog: Solicitar cópia ──────────────────────────────────────────────────

@st.dialog("📦 Solicitar uma cópia do app")
def dialog_solicitar_copia():
    st.markdown(
        "Preencha seus dados e enviaremos o código-fonte completo do app "
        "diretamente no seu e-mail."
    )
    st.divider()

    nome  = st.text_input("Seu nome *", placeholder="Ex: João Silva")
    email = st.text_input("Seu e-mail *", placeholder="joao@email.com")

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        if st.button("📨 Solicitar", type="primary", use_container_width=True):
            # Validações
            if not nome.strip():
                st.error("Informe seu nome.")
                return
            if not email.strip() or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                st.error("Informe um e-mail válido.")
                return

            with st.spinner("Enviando..."):
                ok, msg = enviar_copia(nome.strip(), email.strip(), st.secrets)

            registrar_envio_app("enviado" if ok else "erro")

            if ok:
                st.success(f"✅ Enviado para **{email}**! Verifique sua caixa de entrada.")
            else:
                st.error(f"❌ Não foi possível enviar. Tente novamente mais tarde.\n\n*(Detalhe: {msg})*")

    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


# ─── Navegação personalizada (botões na sidebar) ───────────────────────────────
pg = st.navigation([
    st.Page("pages/home.py",                   title="Patrimônio",                      icon="💼", default=True),
    st.Page("pages/4_Cotacoes.py",             title="Cotações",                         icon="📊"),
    st.Page("pages/1_Importar_Nota.py",        title="Importar Notas de Negociação",     icon="📄"),
    st.Page("pages/5_Informes_Rendimentos.py", title="Importar Informes de Rendimentos", icon="📑"),
    st.Page("pages/3_Auxiliar_IRPF.py",        title="Auxiliar IRPF",                    icon="🧾"),
], position="hidden")  # oculta nav padrão — botões abaixo substituem

with st.sidebar:
    st.markdown("<p style='font-size:2rem; font-weight:700; margin:0; color:#f1f5f9;'>📈 Gestão de Patrimônio</p>", unsafe_allow_html=True)
    st.divider()
    st.page_link("pages/home.py",                   label="💼  Patrimônio",                      use_container_width=True)
    st.page_link("pages/4_Cotacoes.py",             label="📊  Cotações",                         use_container_width=True)
    st.page_link("pages/1_Importar_Nota.py",        label="📄  Importar Notas de Negociação",     use_container_width=True)
    st.page_link("pages/5_Informes_Rendimentos.py", label="📑  Importar Informes de Rendimentos", use_container_width=True)
    st.page_link("pages/3_Auxiliar_IRPF.py",        label="🧾  Auxiliar IRPF",                    use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <style>
    div[data-testid="stSidebar"] .solicitar-btn > button {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
        color: #1a1a1a !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 0.9rem !important;
        box-shadow: 0 2px 12px rgba(245,158,11,0.35) !important;
        transition: all 0.2s !important;
    }
    div[data-testid="stSidebar"] .solicitar-btn > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(245,158,11,0.5) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container(key="solicitar-btn"):
        if st.button("📦 Solicitar uma cópia", use_container_width=True):
            dialog_solicitar_copia()

pg.run()
