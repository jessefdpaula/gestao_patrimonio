"""
Módulo de banco de dados SQLite para o app de Patrimônio.
Usa SQLAlchemy para ORM e criação das tabelas.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "patrimonio.db"


def get_connection():
    """Retorna uma conexão com o banco de dados SQLite."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Retorna linhas como dicionários
    return conn


def init_db():
    """Cria todas as tabelas necessárias se não existirem."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabela de ativos (FIIs, FIAGROs, Ações, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            nome TEXT,
            tipo TEXT NOT NULL,  -- 'FII', 'FIAGRO', 'ACAO', 'RENDA_FIXA', 'CRIPTO'
            cnpj TEXT,
            administrador TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de operações (compras e vendas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            tipo_operacao TEXT NOT NULL,  -- 'COMPRA' ou 'VENDA'
            data_operacao TEXT NOT NULL,
            quantidade REAL NOT NULL,
            preco_unitario REAL NOT NULL,
            valor_total REAL NOT NULL,
            taxas REAL DEFAULT 0.0,
            corretora TEXT,
            nota_negociacao TEXT,  -- número da nota
            origem TEXT DEFAULT 'MANUAL',  -- 'MANUAL', 'PDF', 'IMPORTACAO'
            observacao TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de rendimentos (dividendos, JCP, rendimentos FII)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            data_pagamento TEXT NOT NULL,
            data_com TEXT,  -- data ex-dividendo
            valor_por_cota REAL NOT NULL,
            quantidade_cotas REAL NOT NULL,
            valor_total REAL NOT NULL,
            tipo TEXT DEFAULT 'RENDIMENTO',  -- 'RENDIMENTO', 'JCP', 'DIVIDENDO'
            isento_ir INTEGER DEFAULT 1,  -- FIIs e FIAGROs geralmente isentos
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de renda fixa (dados específicos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS renda_fixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            tipo TEXT NOT NULL,  -- 'CDB', 'LCI', 'LCA', 'TESOURO', etc.
            instituicao TEXT NOT NULL,
            cnpj_instituicao TEXT,
            data_aplicacao TEXT NOT NULL,
            data_vencimento TEXT,
            valor_aplicado REAL NOT NULL,
            taxa_contratada TEXT,  -- ex: "CDI + 0.5%", "IPCA + 5%"
            valor_atual REAL,
            valor_bruto_resgate REAL,
            ir_retido REAL DEFAULT 0.0,
            status TEXT DEFAULT 'ATIVO',  -- 'ATIVO', 'RESGATADO', 'VENCIDO'
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de criptomoedas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cripto_operacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moeda TEXT NOT NULL,  -- 'BTC', 'ETH', etc.
            tipo_operacao TEXT NOT NULL,  -- 'COMPRA', 'VENDA'
            data_operacao TEXT NOT NULL,
            quantidade REAL NOT NULL,
            preco_unitario_brl REAL NOT NULL,
            valor_total_brl REAL NOT NULL,
            exchange TEXT,
            taxa REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de controle de itens declarados no IRPF
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS irpf_declarado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_base TEXT NOT NULL,
            secao TEXT NOT NULL,
            referencia TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(ano_base, secao, referencia)
        )
    """)

    # Tabela de rendimentos tributáveis extraídos de informes de rendimentos (PDF)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informe_tributaveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_calendario TEXT NOT NULL,
            fonte_nome TEXT,
            fonte_cnpj TEXT,
            codigo TEXT,
            tipo TEXT,
            especificacao TEXT,
            valor REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de rendimentos isentos extraídos de informes de rendimentos (PDF)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informe_isentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ano_calendario TEXT NOT NULL,
            fonte_nome TEXT,
            fonte_cnpj TEXT,
            codigo TEXT,
            especificacao TEXT,
            valor REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Log anônimo de envios do app (sem dados pessoais)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_envios_app (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,  -- 'enviado' ou 'erro'
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


def registrar_envio_app(status: str = "enviado"):
    """Grava apenas status + timestamp, sem nenhum dado pessoal."""
    conn = get_connection()
    conn.execute("INSERT INTO log_envios_app (status) VALUES (?)", (status,))
    conn.commit()
    conn.close()


def get_stats_envios() -> dict:
    conn = get_connection()
    total   = conn.execute("SELECT COUNT(*) FROM log_envios_app WHERE status='enviado'").fetchone()[0]
    ultima  = conn.execute("SELECT created_at FROM log_envios_app ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return {"total": total, "ultima": ultima[0] if ultima else None}


# ─── ATIVOS ───────────────────────────────────────────────────────────────────

def upsert_ativo(ticker, nome=None, tipo=None, cnpj=None, administrador=None):
    """Insere ou atualiza informações de um ativo."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
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
    conn = get_connection()
    row = conn.execute("SELECT * FROM ativos WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_todos_ativos():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM ativos ORDER BY tipo, ticker").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── OPERAÇÕES ────────────────────────────────────────────────────────────────

def inserir_operacao(ticker, tipo_operacao, data_operacao, quantidade,
                     preco_unitario, taxas=0.0, corretora=None,
                     nota_negociacao=None, origem="MANUAL", observacao=None):
    """Insere operação. Retorna True se inserida, False se duplicata ignorada."""
    valor_total = quantidade * preco_unitario
    conn = get_connection()

    # Evita duplicata quando a operação vem de uma nota (PDF)
    if nota_negociacao:
        existe = conn.execute("""
            SELECT 1 FROM operacoes
            WHERE ticker = ? AND data_operacao = ? AND quantidade = ?
              AND preco_unitario = ? AND nota_negociacao = ?
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
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM operacoes WHERE ticker = ? ORDER BY data_operacao DESC",
            (ticker,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM operacoes ORDER BY data_operacao DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deletar_operacao(operacao_id):
    conn = get_connection()
    conn.execute("DELETE FROM operacoes WHERE id = ?", (operacao_id,))
    conn.commit()
    conn.close()


# ─── POSIÇÃO (preço médio e quantidade atual) ─────────────────────────────────

def calcular_posicao(ticker):
    """
    Calcula quantidade atual e preço médio ponderado de um ativo.
    Retorna dict com: quantidade, preco_medio, custo_total
    """
    conn = get_connection()
    ops = conn.execute(
        "SELECT * FROM operacoes WHERE ticker = ? ORDER BY data_operacao ASC",
        (ticker,)
    ).fetchall()
    conn.close()

    quantidade = 0.0
    custo_total = 0.0

    for op in ops:
        if op["tipo_operacao"] == "COMPRA":
            custo_total += op["valor_total"] + op["taxas"]
            quantidade += op["quantidade"]
        elif op["tipo_operacao"] == "VENDA":
            if quantidade > 0:
                preco_medio_atual = custo_total / quantidade
                custo_total -= preco_medio_atual * op["quantidade"]
            quantidade -= op["quantidade"]

    preco_medio = (custo_total / quantidade) if quantidade > 0 else 0.0
    return {
        "ticker": ticker,
        "quantidade": quantidade,
        "preco_medio": preco_medio,
        "custo_total": custo_total
    }


def get_carteira_completa():
    """Retorna todas as posições abertas com preço médio."""
    conn = get_connection()
    tickers = conn.execute(
        "SELECT DISTINCT ticker FROM operacoes"
    ).fetchall()
    conn.close()

    carteira = []
    for row in tickers:
        ticker = row["ticker"]
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
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM rendimentos WHERE ticker = ? ORDER BY data_pagamento DESC",
            (ticker,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM rendimentos ORDER BY data_pagamento DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── RENDA FIXA ───────────────────────────────────────────────────────────────

def inserir_renda_fixa(descricao, tipo, instituicao, cnpj_instituicao,
                       data_aplicacao, data_vencimento, valor_aplicado,
                       taxa_contratada, valor_atual=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO renda_fixa
            (descricao, tipo, instituicao, cnpj_instituicao, data_aplicacao,
             data_vencimento, valor_aplicado, taxa_contratada, valor_atual)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (descricao, tipo, instituicao, cnpj_instituicao, data_aplicacao,
          data_vencimento, valor_aplicado, taxa_contratada,
          valor_atual or valor_aplicado))
    conn.commit()
    conn.close()


def get_renda_fixa():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM renda_fixa WHERE status = 'ATIVO' ORDER BY data_vencimento"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def atualizar_valor_renda_fixa(rf_id, valor_atual):
    conn = get_connection()
    conn.execute(
        "UPDATE renda_fixa SET valor_atual = ? WHERE id = ?",
        (valor_atual, rf_id)
    )
    conn.commit()
    conn.close()


# ─── CRIPTO ───────────────────────────────────────────────────────────────────

def inserir_cripto(moeda, tipo_operacao, data_operacao, quantidade,
                   preco_unitario_brl, exchange=None, taxa=0.0):
    valor_total = quantidade * preco_unitario_brl
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


# ─── INFORMES DE RENDIMENTOS ──────────────────────────────────────────────────

def inserir_informe_tributavel(ano_calendario, fonte_nome, fonte_cnpj,
                               codigo, tipo, especificacao, valor):
    """Insere rendimento tributável do informe. Retorna True se inserido, False se duplicata."""
    conn = get_connection()
    existe = conn.execute("""
        SELECT 1 FROM informe_tributaveis
        WHERE ano_calendario = ? AND fonte_cnpj = ? AND codigo = ? AND valor = ?
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
    """Insere rendimento isento do informe. Retorna True se inserido, False se duplicata."""
    conn = get_connection()
    existe = conn.execute("""
        SELECT 1 FROM informe_isentos
        WHERE ano_calendario = ? AND fonte_cnpj = ? AND codigo = ? AND valor = ?
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


# ─── CONTROLE DE DECLARAÇÃO IRPF ─────────────────────────────────────────────

def marcar_declarado(ano_base, secao, referencia):
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO irpf_declarado (ano_base, secao, referencia)
        VALUES (?, ?, ?)
    """, (str(ano_base), secao, referencia))
    conn.commit()
    conn.close()


def desmarcar_declarado(ano_base, secao, referencia):
    conn = get_connection()
    conn.execute("""
        DELETE FROM irpf_declarado WHERE ano_base = ? AND secao = ? AND referencia = ?
    """, (str(ano_base), secao, referencia))
    conn.commit()
    conn.close()


def get_declarados(ano_base, secao):
    conn = get_connection()
    rows = conn.execute(
        "SELECT referencia FROM irpf_declarado WHERE ano_base = ? AND secao = ?",
        (str(ano_base), secao)
    ).fetchall()
    conn.close()
    return {r["referencia"] for r in rows}


def get_declarados_progresso(ano_base):
    """Retorna contagem de declarados por seção para exibir progresso."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT secao, COUNT(*) as total FROM irpf_declarado WHERE ano_base = ? GROUP BY secao",
        (str(ano_base),)
    ).fetchall()
    conn.close()
    return {r["secao"]: r["total"] for r in rows}


def deletar_informe_tributavel(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM informe_tributaveis WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def deletar_informe_isento(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM informe_isentos WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def get_informe_tributaveis(ano_calendario=None):
    conn = get_connection()
    if ano_calendario:
        rows = conn.execute(
            "SELECT * FROM informe_tributaveis WHERE ano_calendario = ? ORDER BY fonte_nome, codigo",
            (str(ano_calendario),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM informe_tributaveis ORDER BY ano_calendario DESC, fonte_nome, codigo"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_informe_isentos(ano_calendario=None):
    conn = get_connection()
    if ano_calendario:
        rows = conn.execute(
            "SELECT * FROM informe_isentos WHERE ano_calendario = ? ORDER BY fonte_nome, codigo",
            (str(ano_calendario),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM informe_isentos ORDER BY ano_calendario DESC, fonte_nome, codigo"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cripto_posicao():
    """Retorna posição atual de cada criptomoeda."""
    conn = get_connection()
    moedas = conn.execute(
        "SELECT DISTINCT moeda FROM cripto_operacoes"
    ).fetchall()
    conn.close()

    posicoes = []
    for row in moedas:
        moeda = row["moeda"]
        conn = get_connection()
        ops = conn.execute(
            "SELECT * FROM cripto_operacoes WHERE moeda = ? ORDER BY data_operacao",
            (moeda,)
        ).fetchall()
        conn.close()

        qtd = 0.0
        custo = 0.0
        for op in ops:
            if op["tipo_operacao"] == "COMPRA":
                qtd += op["quantidade"]
                custo += op["valor_total_brl"]
            else:
                if qtd > 0:
                    pm = custo / qtd
                    custo -= pm * op["quantidade"]
                qtd -= op["quantidade"]

        if qtd > 0:
            posicoes.append({
                "moeda": moeda,
                "quantidade": qtd,
                "preco_medio": custo / qtd,
                "custo_total": custo
            })
    return posicoes
