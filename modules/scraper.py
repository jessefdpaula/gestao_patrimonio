"""
Módulo de Web Scraping para buscar informações de fundos (FII/FIAGRO).
Usa Selenium + requests para buscar CNPJ, nome e administrador.

Fontes:
  - Funds.net (dados de fundos)
  - StatusInvest (fallback)
  - B3 / CVM (oficial)
"""

import re
import time
import requests
from typing import Optional

# Selenium imports com tratamento de erro amigável
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_DISPONIVEL = True
except ImportError:
    SELENIUM_DISPONIVEL = False


# ─── Cache simples em memória ─────────────────────────────────────────────────

_cache_fundos: dict = {}


def _get_cache(ticker: str) -> Optional[dict]:
    return _cache_fundos.get(ticker.upper())


def _set_cache(ticker: str, dados: dict):
    _cache_fundos[ticker.upper()] = dados


# ─── Método 1: API do StatusInvest (mais confiável, sem Selenium) ─────────────

def buscar_via_statusinvest(ticker: str) -> Optional[dict]:
    """
    Busca dados do fundo via StatusInvest.
    Mais rápido que Selenium, usa requests simples.
    """
    url = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        texto = resp.text

        # Extrai CNPJ: padrão XX.XXX.XXX/XXXX-XX
        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto)
        cnpj = cnpj_match.group(1) if cnpj_match else None

        # Extrai nome do fundo
        nome_match = re.search(
            r'<h1[^>]*class="[^"]*lh-4[^"]*"[^>]*>\s*([^<]+)', texto
        )
        if not nome_match:
            nome_match = re.search(r'<title>([^|<]+)', texto)
        nome = nome_match.group(1).strip() if nome_match else ticker

        # Extrai administrador
        admin_match = re.search(
            r'[Aa]dministrador[^<]*<[^>]+>\s*([^<]+)', texto
        )
        administrador = admin_match.group(1).strip() if admin_match else None

        if cnpj:
            return {
                "ticker": ticker.upper(),
                "nome": nome,
                "cnpj": cnpj,
                "administrador": administrador,
                "fonte": "StatusInvest"
            }
    except requests.RequestException:
        pass
    return None


def buscar_via_fundsnet(ticker: str) -> Optional[dict]:
    """
    Busca dados via Funds.NET (base de fundos brasileiros).
    """
    url = f"https://www.fundsexplorer.com.br/funds/{ticker.upper()}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        texto = resp.text

        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto)
        cnpj = cnpj_match.group(1) if cnpj_match else None

        nome_match = re.search(r"<title>([^|<-]+)", texto)
        nome = nome_match.group(1).strip() if nome_match else ticker

        if cnpj:
            return {
                "ticker": ticker.upper(),
                "nome": nome,
                "cnpj": cnpj,
                "administrador": None,
                "fonte": "FundsExplorer"
            }
    except requests.RequestException:
        pass
    return None


# ─── Método 2: Selenium (mais robusto para sites dinâmicos) ──────────────────

def _criar_driver(headless: bool = True) -> Optional["webdriver.Chrome"]:
    """Cria e retorna uma instância do Chrome WebDriver."""
    if not SELENIUM_DISPONIVEL:
        return None
    try:
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,800")
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        # Tenta ChromeDriver padrão do sistema
        driver = webdriver.Chrome(options=opts)
        return driver
    except WebDriverException:
        try:
            # Tenta com webdriver-manager se disponível
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
            return driver
        except Exception:
            return None


def buscar_via_selenium(ticker: str) -> Optional[dict]:
    """
    Busca dados do fundo via Selenium no StatusInvest.
    Usado como fallback quando requests não funcionar.
    """
    if not SELENIUM_DISPONIVEL:
        return None

    driver = _criar_driver(headless=True)
    if not driver:
        return None

    resultado = None
    try:
        url = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
        driver.get(url)

        wait = WebDriverWait(driver, 15)

        # Aguarda carregamento do ticker
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .ticker-name"))
        )
        time.sleep(1)  # aguarda hydration JS

        page_text = driver.find_element(By.TAG_NAME, "body").text

        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", page_text)
        cnpj = cnpj_match.group(1) if cnpj_match else None

        # Nome do fundo
        try:
            nome_el = driver.find_element(By.CSS_SELECTOR, "h1.lh-4, h1")
            nome = nome_el.text.strip()
        except Exception:
            nome = ticker

        # Administrador
        administrador = None
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, ".info-list .item")
            for el in elementos:
                if "administrador" in el.text.lower():
                    partes = el.text.split("\n")
                    if len(partes) > 1:
                        administrador = partes[-1].strip()
                    break
        except Exception:
            pass

        if cnpj:
            resultado = {
                "ticker": ticker.upper(),
                "nome": nome,
                "cnpj": cnpj,
                "administrador": administrador,
                "fonte": "Selenium/StatusInvest"
            }
    except (TimeoutException, WebDriverException, Exception):
        pass
    finally:
        driver.quit()

    return resultado


# ─── Função principal (orquestra as tentativas) ───────────────────────────────

def buscar_info_fundo(ticker: str, usar_selenium: bool = True) -> dict:
    """
    Busca informações completas de um FII ou FIAGRO pelo ticker.

    Tenta na ordem:
    1. Cache (se já buscou antes)
    2. StatusInvest via requests (rápido)
    3. FundsExplorer via requests (fallback)
    4. Selenium (mais lento, último recurso)

    Retorna dict com: ticker, nome, cnpj, administrador, fonte, erro
    """
    ticker = ticker.upper().strip()

    # 1. Cache
    cached = _get_cache(ticker)
    if cached:
        return {**cached, "do_cache": True}

    # 2. StatusInvest via requests
    dados = buscar_via_statusinvest(ticker)

    # 3. FundsExplorer
    if not dados:
        dados = buscar_via_fundsnet(ticker)

    # 4. Selenium
    if not dados and usar_selenium and SELENIUM_DISPONIVEL:
        dados = buscar_via_selenium(ticker)

    if dados:
        _set_cache(ticker, dados)
        return dados

    # Não encontrou
    return {
        "ticker": ticker,
        "nome": None,
        "cnpj": None,
        "administrador": None,
        "fonte": None,
        "erro": (
            f"Não foi possível encontrar informações para {ticker}. "
            "Verifique o ticker ou insira os dados manualmente."
        )
    }


def buscar_info_acao(ticker: str) -> dict:
    """
    Busca informações básicas de uma ação via StatusInvest.
    """
    ticker = ticker.upper().strip()
    cached = _get_cache(ticker)
    if cached:
        return cached

    url = f"https://statusinvest.com.br/acoes/{ticker.lower()}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            texto = resp.text
            cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", texto)
            cnpj = cnpj_match.group(1) if cnpj_match else None
            nome_match = re.search(r"<title>([^|<-]+)", texto)
            nome = nome_match.group(1).strip() if nome_match else ticker
            dados = {
                "ticker": ticker,
                "nome": nome,
                "cnpj": cnpj,
                "administrador": None,
                "fonte": "StatusInvest"
            }
            _set_cache(ticker, dados)
            return dados
    except Exception:
        pass

    return {
        "ticker": ticker,
        "nome": ticker,
        "cnpj": None,
        "fonte": None,
        "erro": f"Não foi possível encontrar dados para {ticker}."
    }
