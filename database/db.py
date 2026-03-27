"""
Módulo de banco de dados do app de Patrimônio.

Suporta dois modos:
  - SQLite (padrão local): dados persistem em data/patrimonio.db
  - Sessão (Streamlit Cloud): dados vivem em st.session_state, somem ao fechar o browser

O modo é detectado automaticamente:
  - Se secrets.toml tiver [app] modo = "sessao"  → modo sessão
  - Caso contrário → SQLite local
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "patrimonio.db"


# ─── Detecção de modo ─────────────────────────────────────────────────────────

def _session_mode() -> bool:
    """Retorna True se o app deve usar st.session_state em vez do SQLite."""
    try:
        import streamlit as st
        return st.secrets.get("app", {}).get("modo") == "sessao"
    except Exception:
        return False


def _db(key: str):
    """Retorna a estrutura de dados da sessão para a chave dada."""
    import streamlit as st
    return st.session_state._patrimonio_db[key]


def _next_id() -> int:
    """Gera um ID único para registros em modo sessão."""
    import streamlit as st
    st.session_state._patrimonio_db["_seq"] += 1
    return st.session_state._patrimonio_db["_seq"]


# ─── Conexão SQLite ───────────────────────────────────────────────────────────

def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ─── Inicialização ────────────────────────────────────────────────────────────

def init_db():
    """Inicializa banco (SQLite ou sessão conforme o modo)."""
    if _session_mode():
        _init_session()
    else:
        _init_sqlite()


def _init_session():
    import streamlit as st
    if "_patrimonio_db" not in st.session_state:
        st.session_state._patrimonio_db = {
            "_seq":               0,
            "ativos":             {},   # ticker → dict
            "operacoes":          [],
            "rendimentos":        [],
            "renda_fixa":         [],
            "cripto":             [],
            "irpf_declarado":     set(),  # {(ano_base, secao, ref)}
            "informe_tributaveis":[],
            "informe_isentos":    [],
            "log_envios":         [],
        }
        # Popula com dados de demonstração na primeira inicialização
        from database.seed_demo import seed_demo
        seed_demo()


def _init_sqlite():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            nome TEXT, tipo TEXT NOT NULL,
            cnpj TEXT, administrador TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            tipo_operacao TEXT NOT NULL,
            data_operacao TEXT NOT NULL,
            quantidade REAL NOT NULL,
            preco_unitario REAL NOT NULL,
            valor_total REAL NOT NULL,
            taxas REAL DEFAULT 0.0,
            corretora TEXT,
            nota_negociacao TEXT,
            origem TEXT DEFAULT 'MANUAL',
            observacao TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data_pagamento TEXT NOT NULL,
            data_com TEXT,
            valor_por_cota REAL NOT NULL,
            quantidade_cotas REAL NOT NULL,
            valor_total REAL NOT NULL,
            tipo TEXT DEFAULT 'RENDIMENTO',
            isento_ir INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS renda_fixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL, tipo TEXT NOT NULL,
            instituicao TEXT NOT NULL, cnpj_instituicao TEXT,
            data_aplicacao TEXT NOT NULL, data_vencimento TEXT,
            valor_aplicado REAL NOT NULL, taxa_contratada TEXT,
            valor_atual REAL, valor_bruto_resgate REAL,
            ir_retido REAL DEFAULT 0.0,
            status TEXT DEFAULT 'ATIVO',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cripto_operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moeda TEXT NOT NULL, tipo_operacao TEXT NOT NULL,
            data_operacao TEXT NOT NULL, quantidade REAL NOT NULL,
            preco_unitario_brl REAL NOT NULL, valor_total_brl REAL NOT NULL,
            exchange TEXT, taxa REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS irpf_declarado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_base TEXT NOT NULL, secao TEXT NOT NULL, referencia TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ano_base, secao, referencia)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informe_tributaveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_calendario TEXT NOT NULL,
            fonte_nome TEXT, fonte_cnpj TEXT, codigo TEXT,
            tipo TEXT, especificacao TEXT, valor REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informe_isentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_calendario TEXT NOT NULL,
            fonte_nome TEXT, fonte_cnpj TEXT, codigo TEXT,
            especificacao TEXT, valor REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_envios_app (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


# ─── Log de envios ────────────────────────────────────────────────────────────

def registrar_envio_app(status: str = "enviado"):
    if _session_mode():
        _db("log_envios").append({"status": status, "created_at": datetime.now().isoformat()})
    else:
        conn = get_connection()
        conn.execute("INSERT INTO log_envios_app (status) VALUES (?)", (status,))
        conn.commit()
        conn.close()


def get_stats_envios() -> dict:
    if _session_mode():
        logs = _db("log_envios")
        total = sum(1 for l in logs if l["status"] == "enviado")
        ultima = logs[-1]["created_at"] if logs else None
        return {"total": total, "ultima": ultima}
    conn = get_connection()
    total  = conn.execute("SELECT COUNT(*) FROM log_envios_app WHERE status='enviado'").fetchone()[0]
    ultima = conn.execute("SELECT created_at FROM log_envios_app ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return {"total": total, "ultima": ultima[0] if ultima else None}


# ─── ATIVOS ───────────────────────────────────────────────────────────────────

def upsert_ativo(ticker, nome=None, tipo=None, cnpj=None, administrador=None):
    if _session_mode():
        existing = _db("ativos").get(ticker, {})
        _db("ativos")[ticker] = {
            "id":           existing.get("id", _next_id()),
            "ticker":       ticker,
            "nome":         nome or existing.get("nome"),
            "tipo":         tipo or existing.get("tipo", "—"),
            "cnpj":         cnpj or existing.get("cnpj"),
            "administrador": administrador or existing.get("administrador"),
            "created_at":   existing.get("created_at", datetime.now().isoformat()),
        }
        return
    conn = get_connection()
    conn.execute("""
        INSERT INTO ativos (ticker, nome, tipo, cnpj, administrador)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            nome = COALESCE(excluded.nome, nome),
            tipo = COALESCE(excluded.tipo, tipo),
            cnpj = COALESCE(excluded.cnpj, cnpj),
            administrador = COALESCE(excluded.administrador, administrador)
    """, (ticker, nome, tipo, cnpj, administrador))
    conn.commit()
    conn.close()


def get_ativo(ticker):
    if _session_mode():
        return _db("ativos").get(ticker)
    conn = get_connection()
    row = conn.execute("SELECT * FROM ativos WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_todos_ativos():
    if _session_mode():
        return sorted(_db("ativos").values(), key=lambda a: (a.get("tipo",""), a.get("ticker","")))
    conn = get_connection()
    rows = conn.execute("SELECT * FROM ativos ORDER BY tipo, ticker").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── OPERAÇÕES ────────────────────────────────────────────────────────────────

def inserir_operacao(ticker, tipo_operacao, data_operacao, quantidade,
                     preco_unitario, taxas=0.0, corretora=None,
                     nota_negociacao=None, origem="MANUAL", observacao=None):
    valor_total = quantidade * preco_unitario

    if _session_mode():
        ops = _db("operacoes")
        if nota_negociacao:
            for op in ops:
                if (op["ticker"] == ticker and op["data_operacao"] == data_operacao
                        and op["quantidade"] == quantidade
                        and op["preco_unitario"] == preco_unitario
                        and op["nota_negociacao"] == nota_negociacao):
                    return False
        ops.append({
            "id": _next_id(), "ticker": ticker,
            "tipo_operacao": tipo_operacao.upper(),
            "data_operacao": data_operacao, "quantidade": quantidade,
            "preco_unitario": preco_unitario, "valor_total": valor_total,
            "taxas": taxas, "corretora": corretora,
            "nota_negociacao": nota_negociacao, "origem": origem,
            "observacao": observacao,
            "created_at": datetime.now().isoformat(),
        })
        return True

    conn = get_connection()
    if nota_negociacao:
        existe = conn.execute("""
            SELECT 1 FROM operacoes
            WHERE ticker=? AND data_operacao=? AND quantidade=?
              AND preco_unitario=? AND nota_negociacao=?
        """, (ticker, data_operacao, quantidade, preco_unitario, nota_negociacao)).fetchone()
        if existe:
            conn.close()
            return False
    conn.execute("""
        INSERT INTO operacoes
            (ticker, tipo_operacao, data_operacao, quantidade, preco_unitario,
             valor_total, taxas, corretora, nota_negociacao, origem, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, tipo_operacao.upper(), data_operacao, quantidade,
          preco_unitario, valor_total, taxas, corretora,
          nota_negociacao, origem, observacao))
    conn.commit()
    conn.close()
    return True


def get_operacoes(ticker=None):
    if _session_mode():
        ops = _db("operacoes")
        if ticker:
            ops = [o for o in ops if o["ticker"] == ticker]
        return sorted(ops, key=lambda o: o["data_operacao"], reverse=True)
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM operacoes WHERE ticker=? ORDER BY data_operacao DESC", (ticker,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM operacoes ORDER BY data_operacao DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deletar_operacao(operacao_id):
    if _session_mode():
        ops = _db("operacoes")
        ops[:] = [o for o in ops if o["id"] != operacao_id]
        return
    conn = get_connection()
    conn.execute("DELETE FROM operacoes WHERE id=?", (operacao_id,))
    conn.commit()
    conn.close()


# ─── POSIÇÃO ──────────────────────────────────────────────────────────────────

def calcular_posicao(ticker):
    ops = get_operacoes(ticker)
    ops = sorted(ops, key=lambda o: o["data_operacao"])
    quantidade = 0.0
    custo_total = 0.0
    for op in ops:
        if op["tipo_operacao"] == "COMPRA":
            custo_total += op["valor_total"] + op["taxas"]
            quantidade  += op["quantidade"]
        elif op["tipo_operacao"] == "VENDA":
            if quantidade > 0:
                pm = custo_total / quantidade
                custo_total -= pm * op["quantidade"]
            quantidade -= op["quantidade"]
    preco_medio = (custo_total / quantidade) if quantidade > 0 else 0.0
    return {"ticker": ticker, "quantidade": quantidade,
            "preco_medio": preco_medio, "custo_total": custo_total}


def get_carteira_completa():
    ops = get_operacoes()
    tickers = list(dict.fromkeys(o["ticker"] for o in ops))
    carteira = []
    for ticker in tickers:
        posicao = calcular_posicao(ticker)
        if posicao["quantidade"] > 0:
            ativo = get_ativo(ticker) or {}
            posicao.update({
                "nome": ativo.get("nome", ticker),
                "tipo": ativo.get("tipo", "—"),
                "cnpj": ativo.get("cnpj", ""),
            })
            carteira.append(posicao)
    return carteira


# ─── RENDIMENTOS ──────────────────────────────────────────────────────────────

def inserir_rendimento(ticker, data_pagamento, valor_por_cota, quantidade_cotas,
                       data_com=None, tipo="RENDIMENTO", isento_ir=True):
    valor_total = valor_por_cota * quantidade_cotas
    if _session_mode():
        _db("rendimentos").append({
            "id": _next_id(), "ticker": ticker,
            "data_pagamento": data_pagamento, "data_com": data_com,
            "valor_por_cota": valor_por_cota, "quantidade_cotas": quantidade_cotas,
            "valor_total": valor_total, "tipo": tipo,
            "isento_ir": int(isento_ir),
            "created_at": datetime.now().isoformat(),
        })
        return
    conn = get_connection()
    conn.execute("""
        INSERT INTO rendimentos
            (ticker, data_pagamento, data_com, valor_por_cota,
             quantidade_cotas, valor_total, tipo, isento_ir)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, data_pagamento, data_com, valor_por_cota,
          quantidade_cotas, valor_total, tipo, int(isento_ir)))
    conn.commit()
    conn.close()


def get_rendimentos(ticker=None):
    if _session_mode():
        r = _db("rendimentos")
        if ticker:
            r = [x for x in r if x["ticker"] == ticker]
        return sorted(r, key=lambda x: x["data_pagamento"], reverse=True)
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM rendimentos WHERE ticker=? ORDER BY data_pagamento DESC", (ticker,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM rendimentos ORDER BY data_pagamento DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── RENDA FIXA ───────────────────────────────────────────────────────────────

def inserir_renda_fixa(descricao, tipo, instituicao, cnpj_instituicao,
                       data_aplicacao, data_vencimento, valor_aplicado,
                       taxa_contratada, valor_atual=None):
    if _session_mode():
        _db("renda_fixa").append({
            "id": _next_id(), "descricao": descricao, "tipo": tipo,
            "instituicao": instituicao, "cnpj_instituicao": cnpj_instituicao,
            "data_aplicacao": data_aplicacao, "data_vencimento": data_vencimento,
            "valor_aplicado": valor_aplicado, "taxa_contratada": taxa_contratada,
            "valor_atual": valor_atual or valor_aplicado,
            "ir_retido": 0.0, "status": "ATIVO",
            "created_at": datetime.now().isoformat(),
        })
        return
    conn = get_connection()
    conn.execute("""
        INSERT INTO renda_fixa
            (descricao, tipo, instituicao, cnpj_instituicao, data_aplicacao,
             data_vencimento, valor_aplicado, taxa_contratada, valor_atual)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (descricao, tipo, instituicao, cnpj_instituicao, data_aplicacao,
          data_vencimento, valor_aplicado, taxa_contratada, valor_atual or valor_aplicado))
    conn.commit()
    conn.close()


def get_renda_fixa():
    if _session_mode():
        return sorted(
            [r for r in _db("renda_fixa") if r.get("status") == "ATIVO"],
            key=lambda r: r.get("data_vencimento", "")
        )
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM renda_fixa WHERE status='ATIVO' ORDER BY data_vencimento"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def atualizar_valor_renda_fixa(rf_id, valor_atual):
    if _session_mode():
        for r in _db("renda_fixa"):
            if r["id"] == rf_id:
                r["valor_atual"] = valor_atual
        return
    conn = get_connection()
    conn.execute("UPDATE renda_fixa SET valor_atual=? WHERE id=?", (valor_atual, rf_id))
    conn.commit()
    conn.close()


# ─── CRIPTO ───────────────────────────────────────────────────────────────────

def inserir_cripto(moeda, tipo_operacao, data_operacao, quantidade,
                   preco_unitario_brl, exchange=None, taxa=0.0):
    valor_total = quantidade * preco_unitario_brl
    if _session_mode():
        _db("cripto").append({
            "id": _next_id(), "moeda": moeda,
            "tipo_operacao": tipo_operacao.upper(),
            "data_operacao": data_operacao, "quantidade": quantidade,
            "preco_unitario_brl": preco_unitario_brl,
            "valor_total_brl": valor_total,
            "exchange": exchange, "taxa": taxa,
            "created_at": datetime.now().isoformat(),
        })
        return
    conn = get_connection()
    conn.execute("""
        INSERT INTO cripto_operacoes
            (moeda, tipo_operacao, data_operacao, quantidade,
             preco_unitario_brl, valor_total_brl, exchange, taxa)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (moeda, tipo_operacao.upper(), data_operacao, quantidade,
          preco_unitario_brl, valor_total, exchange, taxa))
    conn.commit()
    conn.close()


def get_cripto_posicao():
    if _session_mode():
        ops = _db("cripto")
    else:
        conn = get_connection()
        ops = [dict(r) for r in conn.execute(
            "SELECT * FROM cripto_operacoes ORDER BY data_operacao"
        ).fetchall()]
        conn.close()

    moedas = list(dict.fromkeys(o["moeda"] for o in ops))
    posicoes = []
    for moeda in moedas:
        m_ops = sorted([o for o in ops if o["moeda"] == moeda], key=lambda o: o["data_operacao"])
        qtd = custo = 0.0
        for op in m_ops:
            if op["tipo_operacao"] == "COMPRA":
                qtd   += op["quantidade"]
                custo += op["valor_total_brl"]
            else:
                if qtd > 0:
                    custo -= (custo / qtd) * op["quantidade"]
                qtd -= op["quantidade"]
        if qtd > 0:
            posicoes.append({"moeda": moeda, "quantidade": qtd,
                             "preco_medio": custo / qtd, "custo_total": custo})
    return posicoes


# ─── INFORMES DE RENDIMENTOS ──────────────────────────────────────────────────

def inserir_informe_tributavel(ano_calendario, fonte_nome, fonte_cnpj,
                               codigo, tipo, especificacao, valor):
    if _session_mode():
        for r in _db("informe_tributaveis"):
            if (r["ano_calendario"] == str(ano_calendario)
                    and r["fonte_cnpj"] == fonte_cnpj
                    and r["codigo"] == codigo
                    and r["valor"] == valor):
                return False
        _db("informe_tributaveis").append({
            "id": _next_id(), "ano_calendario": str(ano_calendario),
            "fonte_nome": fonte_nome, "fonte_cnpj": fonte_cnpj,
            "codigo": codigo, "tipo": tipo, "especificacao": especificacao,
            "valor": valor, "created_at": datetime.now().isoformat(),
        })
        return True
    conn = get_connection()
    existe = conn.execute("""
        SELECT 1 FROM informe_tributaveis
        WHERE ano_calendario=? AND fonte_cnpj=? AND codigo=? AND valor=?
    """, (ano_calendario, fonte_cnpj, codigo, valor)).fetchone()
    if existe:
        conn.close()
        return False
    conn.execute("""
        INSERT INTO informe_tributaveis
            (ano_calendario, fonte_nome, fonte_cnpj, codigo, tipo, especificacao, valor)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ano_calendario, fonte_nome, fonte_cnpj, codigo, tipo, especificacao, valor))
    conn.commit()
    conn.close()
    return True


def inserir_informe_isento(ano_calendario, fonte_nome, fonte_cnpj,
                           codigo, especificacao, valor):
    if _session_mode():
        for r in _db("informe_isentos"):
            if (r["ano_calendario"] == str(ano_calendario)
                    and r["fonte_cnpj"] == fonte_cnpj
                    and r["codigo"] == codigo
                    and r["valor"] == valor):
                return False
        _db("informe_isentos").append({
            "id": _next_id(), "ano_calendario": str(ano_calendario),
            "fonte_nome": fonte_nome, "fonte_cnpj": fonte_cnpj,
            "codigo": codigo, "especificacao": especificacao,
            "valor": valor, "created_at": datetime.now().isoformat(),
        })
        return True
    conn = get_connection()
    existe = conn.execute("""
        SELECT 1 FROM informe_isentos
        WHERE ano_calendario=? AND fonte_cnpj=? AND codigo=? AND valor=?
    """, (ano_calendario, fonte_cnpj, codigo, valor)).fetchone()
    if existe:
        conn.close()
        return False
    conn.execute("""
        INSERT INTO informe_isentos
            (ano_calendario, fonte_nome, fonte_cnpj, codigo, especificacao, valor)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ano_calendario, fonte_nome, fonte_cnpj, codigo, especificacao, valor))
    conn.commit()
    conn.close()
    return True


def deletar_informe_tributavel(item_id):
    if _session_mode():
        lst = _db("informe_tributaveis")
        lst[:] = [r for r in lst if r["id"] != item_id]
        return
    conn = get_connection()
    conn.execute("DELETE FROM informe_tributaveis WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


def deletar_informe_isento(item_id):
    if _session_mode():
        lst = _db("informe_isentos")
        lst[:] = [r for r in lst if r["id"] != item_id]
        return
    conn = get_connection()
    conn.execute("DELETE FROM informe_isentos WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


def get_informe_tributaveis(ano_calendario=None):
    if _session_mode():
        r = _db("informe_tributaveis")
        if ano_calendario:
            r = [x for x in r if x["ano_calendario"] == str(ano_calendario)]
        return sorted(r, key=lambda x: (x["ano_calendario"], x.get("fonte_nome",""), x.get("codigo","")), reverse=True)
    conn = get_connection()
    if ano_calendario:
        rows = conn.execute(
            "SELECT * FROM informe_tributaveis WHERE ano_calendario=? ORDER BY fonte_nome, codigo",
            (str(ano_calendario),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM informe_tributaveis ORDER BY ano_calendario DESC, fonte_nome, codigo"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_informe_isentos(ano_calendario=None):
    if _session_mode():
        r = _db("informe_isentos")
        if ano_calendario:
            r = [x for x in r if x["ano_calendario"] == str(ano_calendario)]
        return sorted(r, key=lambda x: (x["ano_calendario"], x.get("fonte_nome",""), x.get("codigo","")), reverse=True)
    conn = get_connection()
    if ano_calendario:
        rows = conn.execute(
            "SELECT * FROM informe_isentos WHERE ano_calendario=? ORDER BY fonte_nome, codigo",
            (str(ano_calendario),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM informe_isentos ORDER BY ano_calendario DESC, fonte_nome, codigo"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── IRPF DECLARADO ───────────────────────────────────────────────────────────

def marcar_declarado(ano_base, secao, referencia):
    if _session_mode():
        _db("irpf_declarado").add((str(ano_base), secao, referencia))
        return
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO irpf_declarado (ano_base, secao, referencia)
        VALUES (?, ?, ?)
    """, (str(ano_base), secao, referencia))
    conn.commit()
    conn.close()


def desmarcar_declarado(ano_base, secao, referencia):
    if _session_mode():
        _db("irpf_declarado").discard((str(ano_base), secao, referencia))
        return
    conn = get_connection()
    conn.execute("""
        DELETE FROM irpf_declarado WHERE ano_base=? AND secao=? AND referencia=?
    """, (str(ano_base), secao, referencia))
    conn.commit()
    conn.close()


def get_declarados(ano_base, secao):
    if _session_mode():
        return {ref for (ab, s, ref) in _db("irpf_declarado")
                if ab == str(ano_base) and s == secao}
    conn = get_connection()
    rows = conn.execute(
        "SELECT referencia FROM irpf_declarado WHERE ano_base=? AND secao=?",
        (str(ano_base), secao)
    ).fetchall()
    conn.close()
    return {r["referencia"] for r in rows}


def get_declarados_progresso(ano_base):
    if _session_mode():
        contagem = {}
        for (ab, secao, _) in _db("irpf_declarado"):
            if ab == str(ano_base):
                contagem[secao] = contagem.get(secao, 0) + 1
        return contagem
    conn = get_connection()
    rows = conn.execute(
        "SELECT secao, COUNT(*) as total FROM irpf_declarado WHERE ano_base=? GROUP BY secao",
        (str(ano_base),)
    ).fetchall()
    conn.close()
    return {r["secao"]: r["total"] for r in rows}
