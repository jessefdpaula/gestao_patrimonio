"""
Extrator inteligente de informes de rendimentos via LLM (Groq / Llama 3).

Substitui os parsers fixos por banco: qualquer informe em português
é compreendido automaticamente pelo modelo, que retorna JSON estruturado
com os campos do IRPF.

Fluxo:
  texto_bruto (pypdf) → Groq LLM → JSON → mesmo formato dos parsers antigos

Fallback: se a IA falhar (sem chave, timeout, JSON inválido), o sistema
usa automaticamente os parsers regex tradicionais.
"""

import json
import re
import streamlit as st

try:
    from groq import Groq
    _GROQ_DISPONIVEL = True
except ImportError:
    _GROQ_DISPONIVEL = False


# ─── Prompt especializado em IRPF ────────────────────────────────────────────

_SYSTEM_PROMPT = """Você é um especialista em Imposto de Renda Pessoa Física (IRPF) no Brasil.
Sua tarefa é extrair informações financeiras de informes de rendimentos e retornar APENAS um JSON válido.
Não adicione explicações, markdown ou texto fora do JSON.
Valores monetários devem ser números float (ex: 1234.56), nunca strings.
Se um campo não existir no documento, use null ou lista vazia."""

_USER_PROMPT = """Analise o informe de rendimentos abaixo e extraia os dados no formato JSON especificado.

TEXTO DO INFORME:
{texto}

Retorne EXATAMENTE este JSON (sem texto adicional):
{{
  "fonte_pagadora": {{
    "nome": "nome da instituição financeira",
    "cnpj": "XX.XXX.XXX/XXXX-XX"
  }},
  "titular": "nome do beneficiário",
  "cpf": "CPF do beneficiário",
  "ano_calendario": 2025,
  "rendimentos_tributaveis": [
    {{
      "codigo": "código IRPF se disponível",
      "especificacao": "descrição do rendimento",
      "valor": 0.00
    }}
  ],
  "rendimentos_isentos": [
    {{
      "codigo": "código IRPF se disponível",
      "especificacao": "descrição do rendimento isento",
      "valor": 0.00
    }}
  ],
  "bens_direitos": [
    {{
      "grupo": "grupo IRPF (ex: 04)",
      "codigo_tipo": "código tipo (ex: 02)",
      "especificacao": "descrição do bem ou direito",
      "saldo_anterior": 0.00,
      "saldo_base": 0.00
    }}
  ],
    "criptomoedas": [
    {{
      "nome": "nome da criptomoeda (ex: Bitcoin)",
      "ticker": "símbolo (ex: BTC)",
      "data": "DD/MM/AAAA",
      "quantidade": 0.00000000,
      "saldo_reais": 0.00,
      "custo_medio_aquisicao": 0.00
    }}
  ]
}}

Regras importantes:
- Rendimentos ISENTOS: poupança, dividendos, FII/FIAgro, LCI/LCA, debêntures incentivadas
- Rendimentos TRIBUTÁVEIS: CDB, RDB, salários, JCP (juros sobre capital próprio)
- Rendimentos de TRIBUTAÇÃO EXCLUSIVA (13º salário, aplicações financeiras em geral): inclua em tributaveis com especificacao clara
- Bens e Direitos: inclua saldos de contas, aplicações, ações, fundos
- Se houver múltiplas fontes pagadoras no documento, use a principal (maior valor)
- Extraia TODOS os valores encontrados, mesmo que zerados
"""


def _limpar_json(texto: str) -> str:
    """Remove markdown code fences e texto antes/após o JSON."""
    # Remove ```json ... ``` ou ``` ... ```
    texto = re.sub(r"```(?:json)?\s*", "", texto)
    texto = re.sub(r"```\s*", "", texto)
    # Pega apenas o bloco JSON (do primeiro { ao último })
    inicio = texto.find("{")
    fim    = texto.rfind("}") + 1
    if inicio >= 0 and fim > inicio:
        return texto[inicio:fim]
    return texto.strip()


def _formatar_resultado(dados: dict) -> dict:
    """Converte o JSON do LLM para o formato padrão do app."""
    resultado = {
        "titular":              dados.get("titular"),
        "cpf":                  dados.get("cpf"),
        "ano_calendario":       dados.get("ano_calendario"),
        "parser_usado":         "IA — Groq / Llama 3.3",
        "fontes_pagadoras":     [],
        "rendimentos_tributaveis": [],
        "rendimentos_isentos":  [],
        "bens_direitos":        [],
        "criptomoedas":         [],
        "total_tributavel":     0.0,
        "total_isento":         0.0,
        "texto_bruto":          "",
        "erro":                 None,
    }

    # Fonte pagadora
    fp = dados.get("fonte_pagadora") or {}
    if fp.get("nome") or fp.get("cnpj"):
        resultado["fontes_pagadoras"].append({
            "nome": fp.get("nome", ""),
            "cnpj": fp.get("cnpj", ""),
        })

    # Rendimentos tributáveis
    for r in dados.get("rendimentos_tributaveis") or []:
        valor = float(r.get("valor") or 0)
        resultado["rendimentos_tributaveis"].append({
            "codigo":       r.get("codigo", ""),
            "tipo":         "Tributável",
            "especificacao": r.get("especificacao", ""),
            "valor":        valor,
        })

    # Rendimentos isentos
    for r in dados.get("rendimentos_isentos") or []:
        valor = float(r.get("valor") or 0)
        resultado["rendimentos_isentos"].append({
            "codigo":       r.get("codigo", ""),
            "tipo":         "Isento",
            "especificacao": r.get("especificacao", ""),
            "valor":        valor,
        })

    # Bens e direitos
    for b in dados.get("bens_direitos") or []:
        resultado["bens_direitos"].append({
            "grupo":        b.get("grupo", ""),
            "codigo_tipo":  b.get("codigo_tipo", ""),
            "especificacao": b.get("especificacao", ""),
            "saldo_anterior": float(b.get("saldo_anterior") or 0),
            "saldo_base":     float(b.get("saldo_base") or 0),
        })

    resultado["total_tributavel"] = sum(r["valor"] for r in resultado["rendimentos_tributaveis"])
    resultado["total_isento"]     = sum(r["valor"] for r in resultado["rendimentos_isentos"])

    return resultado


def extrair_com_ia(texto: str) -> dict | None:
    """
    Tenta extrair dados do informe usando o LLM Groq.

    Retorna o dict no formato padrão, ou None se falhar
    (sem chave, quota excedida, JSON inválido, etc.).
    """
    if not _GROQ_DISPONIVEL:
        return None

    # Pega a chave do st.secrets (sem quebrar se não existir)
    try:
        api_key = st.secrets["groq"]["api_key"]
    except Exception:
        return None

    if not api_key:
        return None

    # Limita texto para não exceder contexto do modelo (~6000 chars)
    texto_recortado = texto[:6000]

    try:
        client   = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model       = "llama-3.3-70b-versatile",
            temperature = 0.1,
            max_tokens  = 2048,
            messages    = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": _USER_PROMPT.format(texto=texto_recortado)},
            ],
        )
        conteudo = response.choices[0].message.content or ""
        json_str = _limpar_json(conteudo)
        dados    = json.loads(json_str)
        return _formatar_resultado(dados)

    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def ia_disponivel() -> bool:
    """Verifica se a IA está configurada e o SDK está instalado."""
    if not _GROQ_DISPONIVEL:
        return False
    try:
        chave = st.secrets["groq"]["api_key"]
        return bool(chave)
    except Exception:
        return False
