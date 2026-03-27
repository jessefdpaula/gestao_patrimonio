"""
Registry de parsers de PDF para o patrimonio_app.

Como adicionar suporte a uma nova corretora
==========================================

1. Crie um arquivo nesta pasta. Use o nome no formato:
     <corretora>_nota.py   — para notas de negociação
     <corretora>_informe.py — para informes de rendimentos

2. Implemente a classe herdando de NotaParser ou InformeParser (base.py).

3. Importe e adicione à lista abaixo.

Exemplo (XP Investimentos nota):
    # xp_nota.py
    from .base import NotaParser, limpar_valor, determinar_tipo_ativo
    from .nubank_nota import parse_bovespa_padrao   # reutiliza o mesmo parser se o formato for BOVESPA

    class XpNotaParser(NotaParser):
        NOME = "XP Investimentos"
        PRIORIDADE = 20

        @classmethod
        def detectar(cls, texto: str) -> bool:
            return "xp investimentos" in texto.lower()

        @classmethod
        def parsear(cls, texto: str) -> dict:
            return parse_bovespa_padrao(texto, corretora="XP")

    # Depois, adicione em _PARSERS_NOTA abaixo:
    from .xp_nota import XpNotaParser
    _PARSERS_NOTA = [NubankNotaParser, XpNotaParser, GenericoNotaParser]
"""

from .nubank_nota import NubankNotaParser
from .generico_nota import GenericoNotaParser
from .nubank_informe import NubankInformeParser
from .bradesco_informe import BradescoInformeParser
from .ct01_informe import CT01InformeParser
from .generico_informe import GenericoInformeParser

# ─── Registros (ordem = prioridade de detecção) ───────────────────────────────
# Parsers específicos ANTES do genérico. O genérico sempre retorna True.

_PARSERS_NOTA = sorted(
    [NubankNotaParser, GenericoNotaParser],
    key=lambda p: p.PRIORIDADE,
)

_PARSERS_INFORME = sorted(
    [NubankInformeParser, BradescoInformeParser, CT01InformeParser, GenericoInformeParser],
    key=lambda p: p.PRIORIDADE,
)


# ─── API pública ──────────────────────────────────────────────────────────────

def get_parser_nota(texto: str):
    """Retorna a classe de parser mais adequada para o texto da nota."""
    for parser in _PARSERS_NOTA:
        if parser.detectar(texto):
            return parser
    return GenericoNotaParser


def get_parser_informe(texto: str):
    """Retorna a classe de parser mais adequada para o texto do informe."""
    for parser in _PARSERS_INFORME:
        if parser.detectar(texto):
            return parser
    return GenericoInformeParser


def listar_parsers_nota() -> list[dict]:
    """Lista todos os parsers de nota registrados (para debug/UI)."""
    return [{"nome": p.NOME, "prioridade": p.PRIORIDADE} for p in _PARSERS_NOTA]


def listar_parsers_informe() -> list[dict]:
    """Lista todos os parsers de informe registrados (para debug/UI)."""
    return [{"nome": p.NOME, "prioridade": p.PRIORIDADE} for p in _PARSERS_INFORME]
