"""
Classes base e helpers compartilhados para todos os parsers de PDF.

Para criar um novo parser:
1. Crie um arquivo nesta pasta (ex: xp_nota.py)
2. Herde de NotaParser ou InformeParser
3. Implemente detectar() e parsear()
4. Registre no __init__.py

Exemplo mínimo para nota:
    from .base import NotaParser

    class XpNotaParser(NotaParser):
        NOME = "XP Investimentos"
        PRIORIDADE = 10  # menor = testado antes do genérico (100)

        @classmethod
        def detectar(cls, texto: str) -> bool:
            return "xp investimentos" in texto.lower()

        @classmethod
        def parsear(cls, texto: str) -> dict:
            # retorna dict no formato padrão de ler_nota_pdf()
            ...
"""

from abc import ABC, abstractmethod
import re


# ─── Classes base ─────────────────────────────────────────────────────────────

class NotaParser(ABC):
    """Interface para parsers de Nota de Negociação."""

    NOME: str = "Genérico"
    PRIORIDADE: int = 100  # menor número = testado primeiro no registry

    @classmethod
    @abstractmethod
    def detectar(cls, texto: str) -> bool:
        """Retorna True se este parser reconhece o formato do PDF."""

    @classmethod
    @abstractmethod
    def parsear(cls, texto: str) -> dict:
        """
        Extrai dados da nota.

        Retorna dict com chaves:
          numero_nota, data_pregao, corretora, operacoes,
          taxa_liquidacao, emolumentos, liquido
        """


class InformeParser(ABC):
    """Interface para parsers de Informe de Rendimentos."""

    NOME: str = "Genérico"
    PRIORIDADE: int = 100

    @classmethod
    @abstractmethod
    def detectar(cls, texto: str) -> bool:
        """Retorna True se este parser reconhece o formato do PDF."""

    @classmethod
    @abstractmethod
    def parsear(cls, texto: str, ano_ant: str, ano_base: str) -> dict:
        """
        Extrai dados do informe.

        Retorna dict com chaves:
          fontes_pagadoras, rendimentos_tributaveis, rendimentos_isentos,
          bens_direitos, criptomoedas
        """


# ─── Helpers compartilhados ───────────────────────────────────────────────────

def limpar_valor(texto: str) -> float:
    """Converte 'R$ 1.234,56' ou '1.234,56' para float."""
    if not texto:
        return 0.0
    texto = re.sub(r"R\$\s*", "", str(texto)).strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def extrair_cnpj(texto: str) -> str | None:
    match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    return match.group(0) if match else None


def extrair_cpf(texto: str) -> str | None:
    match = re.search(r"\d{3}\.\*\*\*\.\*\*\*-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", texto)
    return match.group(0) if match else None


def determinar_tipo_ativo(ticker: str) -> str:
    """Infere tipo de ativo pelo padrão do ticker brasileiro."""
    ticker = ticker.upper()
    fiagros_conhecidos = {"SNAG", "MGHT", "RURA", "FIAG", "HGAG", "AGRX"}
    base = re.sub(r"\d+$", "", ticker)
    if base in fiagros_conhecidos:
        return "FIAGRO"
    if re.match(r"^[A-Z]{4}11$", ticker):
        return "FII"
    if re.match(r"^[A-Z]{4}\d{1,2}$", ticker):
        return "ACAO"
    return "ACAO"
