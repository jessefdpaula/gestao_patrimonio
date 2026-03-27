# 💼 Gestão de Patrimônio

Aplicativo web para controle de investimentos e auxílio na declaração do **Imposto de Renda Pessoa Física (IRPF)**, desenvolvido com [Streamlit](https://streamlit.io).

---

## Funcionalidades

- 📊 **Dashboard** — visão geral do patrimônio consolidado com cotações em tempo real
- 📄 **Importar Notas de Negociação** — leitura automática de PDFs de corretoras (Nubank, XP, Clear e outras)
- 📑 **Importar Informes de Rendimentos** — leitura inteligente via IA de PDFs de qualquer banco ou corretora
- 🧾 **Auxiliar IRPF** — relatório completo com bens e direitos, rendimentos isentos, tributáveis e ganho de capital, com marcação de itens já declarados
- 📈 **Cotações** — consulta de preços de ações e FIIs via API
- 📦 **Solicitar uma cópia** — envio automático do app por e-mail para interessados

---

## Extração Inteligente com IA

Os informes de rendimentos são processados por um **LLM (Llama 3.3 via Groq)** que lê e interpreta o documento automaticamente, sem depender de parsers fixos por banco. Funciona com qualquer instituição financeira brasileira.

```
PDF (qualquer banco) → texto → 🤖 Llama 3.3 → JSON estruturado → app
```

Caso a IA não esteja configurada, o sistema utiliza parsers regex como fallback para os formatos conhecidos.

---

## Instalação

### Pré-requisitos
- Python 3.10+
- pip

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/jessefdpaula/gestao_patrimonio.git
cd gestao_patrimonio

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure os secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml com suas chaves

# 5. Execute o app
streamlit run app.py
```

---

## Configuração (`secrets.toml`)

Renomeie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha:

```toml
[groq]
api_key = "gsk_..."          # Chave gratuita em console.groq.com

[email]
resend_api_key = "re_..."    # Chave gratuita em resend.com (opcional)
from_address   = "voce@seudominio.com"
from_name      = "Gestão de Patrimônio"
owner_email    = "voce@gmail.com"
```

### Obtendo as chaves

| Serviço | Link | Gratuito |
|---|---|:---:|
| **Groq** (IA para informes) | [console.groq.com](https://console.groq.com) | ✅ |
| **Resend** (envio de e-mail) | [resend.com](https://resend.com) | ✅ |

---

## Estrutura do projeto

```
gestao_patrimonio/
├── app.py                         ← ponto de entrada Streamlit
├── pages/
│   ├── home.py                    ← dashboard
│   ├── 1_Importar_Nota.py
│   ├── 3_Auxiliar_IRPF.py
│   ├── 4_Cotacoes.py
│   └── 5_Informes_Rendimentos.py
├── modules/
│   ├── ai_extractor.py            ← extração via IA (Groq / Llama 3.3)
│   ├── nota_negociacao.py
│   ├── informe_rendimentos.py
│   ├── ir_helper.py
│   ├── cotacoes.py
│   ├── email_sender.py
│   └── parsers/                   ← parsers regex (fallback)
│       ├── nubank_informe.py
│       ├── bradesco_informe.py
│       ├── ct01_informe.py
│       └── generico_informe.py
├── database/
│   └── db.py                      ← SQLite (criado automaticamente)
├── data/                          ← banco de dados local (não versionado)
├── requirements.txt
└── .streamlit/
    └── secrets.toml.example
```

---

## Tecnologias

| Categoria | Tecnologia |
|---|---|
| Interface | [Streamlit](https://streamlit.io) |
| IA / LLM | [Groq](https://groq.com) + Llama 3.3 70B |
| Leitura de PDF | [pypdf](https://pypdf.readthedocs.io) + [pdfplumber](https://github.com/jsvine/pdfplumber) |
| Dados | [pandas](https://pandas.pydata.org) + SQLite |
| Cotações | [yfinance](https://github.com/ranaroussi/yfinance) |
| E-mail | [Resend](https://resend.com) |

---

## Aviso legal

Este aplicativo é uma ferramenta de **apoio** à declaração do IRPF. Os dados gerados devem ser conferidos pelo contribuinte. O autor não se responsabiliza por eventuais erros na declaração.

---

## Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.
