"""
Módulo para buscar cotações em tempo real e históricas.
Usa yfinance (Yahoo Finance) para ações e fundos brasileiros.
"""

from datetime import datetime, timedelta
from typing import Optional
import time

try:
    import yfinance as yf
    YFINANCE_DISPONIVEL = True
except ImportError:
    YFINANCE_DISPONIVEL = False

# Cache simples de cotações (evita requests repetidos)
_cache_cotacoes: dict = {}
_CACHE_TTL_SEGUNDOS = 300  # 5 minutos


def _ticker_yahoo(ticker: str) -> str:
    """
    Converte ticker brasileiro para o formato do Yahoo Finance.
    Ex: KNCR11 → KNCR11.SA | BTC → BTC-BRL
    """
    ticker = ticker.upper().strip()
    # Criptomoedas
    criptos = {"BTC", "ETH", "SOL", "BNB", "ADA", "DOT", "MATIC", "AVAX", "XRP"}
    if ticker in criptos:
        return f"{ticker}-BRL"
    # Ativos brasileiros B3
    if not ticker.endswith(".SA") and re.match(r"^[A-Z]{4}\d{1,2}$", ticker):
        return f"{ticker}.SA"
    return ticker


import re


def get_cotacao_atual(ticker: str) -> Optional[float]:
    """
    Retorna o preço atual de um ativo.
    Usa cache de 5 minutos para não sobrecarregar a API.
    """
    if not YFINANCE_DISPONIVEL:
        return None

    # Verifica cache
    agora = time.time()
    if ticker in _cache_cotacoes:
        preco, timestamp = _cache_cotacoes[ticker]
        if agora - timestamp < _CACHE_TTL_SEGUNDOS:
            return preco

    try:
        ticker_yf = _ticker_yahoo(ticker)
        ativo = yf.Ticker(ticker_yf)
        info = ativo.fast_info

        # fast_info é mais rápido que info completo
        preco = getattr(info, "last_price", None)
        if preco and preco > 0:
            _cache_cotacoes[ticker] = (preco, agora)
            return round(preco, 2)

        # Fallback: histórico recente
        hist = ativo.history(period="2d")
        if not hist.empty:
            preco = float(hist["Close"].iloc[-1])
            _cache_cotacoes[ticker] = (preco, agora)
            return round(preco, 2)
    except Exception:
        pass
    return None


def get_cotacoes_lote(tickers: list) -> dict:
    """
    Busca cotações de múltiplos ativos de uma vez (mais eficiente).
    Retorna: {ticker: preco, ...}
    """
    if not YFINANCE_DISPONIVEL or not tickers:
        return {}

    resultado = {}
    tickers_yf = [_ticker_yahoo(t) for t in tickers]
    mapa = dict(zip(tickers_yf, tickers))

    try:
        # Download em lote é muito mais rápido
        import yfinance as yf
        dados = yf.download(
            tickers=" ".join(tickers_yf),
            period="2d",
            progress=False,
            group_by="ticker",
            auto_adjust=True
        )

        for ticker_yf, ticker_orig in mapa.items():
            try:
                if len(tickers_yf) == 1:
                    preco = float(dados["Close"].iloc[-1])
                else:
                    preco = float(dados["Close"][ticker_yf].dropna().iloc[-1])
                resultado[ticker_orig] = round(preco, 2)
            except Exception:
                resultado[ticker_orig] = None
    except Exception:
        # Fallback individual
        for ticker in tickers:
            resultado[ticker] = get_cotacao_atual(ticker)

    return resultado


def get_historico(ticker: str, periodo: str = "1y") -> Optional[object]:
    """
    Retorna histórico de preços como DataFrame pandas.

    Períodos válidos: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    """
    if not YFINANCE_DISPONIVEL:
        return None
    try:
        ticker_yf = _ticker_yahoo(ticker)
        ativo = yf.Ticker(ticker_yf)
        hist = ativo.history(period=periodo)
        if hist.empty:
            return None
        hist.index = hist.index.tz_localize(None)  # Remove timezone
        return hist
    except Exception:
        return None


def calcular_variacao(ticker: str) -> dict:
    """
    Calcula variações do dia, semana, mês e ano.
    Retorna dict com: preco_atual, var_dia, var_semana, var_mes, var_ano
    """
    resultado = {
        "preco_atual": None,
        "var_dia": None,
        "var_semana": None,
        "var_mes": None,
        "var_ano": None
    }

    if not YFINANCE_DISPONIVEL:
        return resultado

    try:
        ticker_yf = _ticker_yahoo(ticker)
        ativo = yf.Ticker(ticker_yf)
        hist = ativo.history(period="1y")

        if hist.empty:
            return resultado

        preco_atual = float(hist["Close"].iloc[-1])
        resultado["preco_atual"] = round(preco_atual, 2)

        def var_pct(idx):
            if len(hist) > idx:
                p_ant = float(hist["Close"].iloc[-(idx + 1)])
                if p_ant > 0:
                    return round((preco_atual - p_ant) / p_ant * 100, 2)
            return None

        resultado["var_dia"] = var_pct(1)
        resultado["var_semana"] = var_pct(5)
        resultado["var_mes"] = var_pct(21)
        resultado["var_ano"] = var_pct(252)

    except Exception:
        pass

    return resultado


def get_cotacao_cripto(moeda: str) -> Optional[float]:
    """Busca cotação de cripto em BRL."""
    return get_cotacao_atual(moeda)
