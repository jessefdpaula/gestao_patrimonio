# 💼 Gestão de Patrimônio

Aplicativo web para controle de investimentos e auxílio na declaração do **Imposto de Renda Pessoa Física (IRPF)**, desenvolvido com [Streamlit](https://streamlit.io).

---

## Funcionalidades

- 📊 **Dashboard** — visão geral do patrimônio consolidado com cotações em tempo real
- 📄 **Importar Notas de Negociação** — leitura automática de PDFs de corretoras (Nubank, XP, Clear e outras)
- 📑 **Importar Informes de Rendimentos** — leitura de PDFs de bancos e corretoras (Nubank, Bradesco, formato genérico, CT01)
- 🧾 **Auxiliar IRPF** — geração de relatório completo com bens e direitos, rendimentos isentos, tributáveis e ganho de capital, com marcação de itens já declarados
- 📈 **Cotações** — consulta de preços de ações e FIIs via API

---

## Instalação

### Pré-requisitos
- Python 3.10+
- pip

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/gestao-patrimonio.git
cd gestao-patrimonio

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure os secrets (opcional — apenas para envio de e-mail)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml com sua chave Resend

# 5. Execute o app
streamlit run app.py
```

---

## Configuração de E-mail (opcional)

O app permite que visitantes solicitem uma cópia via e-mail. Para ativar:

1. Crie uma conta gratuita em [resend.com](https://resend.com)
2. Gere uma API Key
3. Preencha `.streamlit/secrets.toml` com a chave (veja `.streamlit/secrets.toml.example`)

---

## Corretoras / Bancos suportados

| Instituição | Nota de Negociação | Informe de Rendimentos |
|---|:---:|:---:|
| Nubank / Nu Invest | ✅ | ✅ |
| Bradesco | — | ✅ |
| Ágora | — | ✅ |
| Formato genérico | ✅ | ✅ |
| CT01 (comprovante empregador) | — | ✅ |

---

## Estrutura do projeto

```
gestao_patrimonio/
├── app.py                    ← ponto de entrada Streamlit
├── pages/
│   ├── home.py               ← dashboard
│   ├── 1_Importar_Nota.py
│   ├── 3_Auxiliar_IRPF.py
│   ├── 4_Cotacoes.py
│   └── 5_Informes_Rendimentos.py
├── modules/
│   ├── nota_negociacao.py
│   ├── informe_rendimentos.py
│   ├── ir_helper.py
│   ├── cotacoes.py
│   ├── email_sender.py
│   └── parsers/              ← parsers por corretora/banco
├── database/
│   └── db.py                 ← SQLite (criado automaticamente)
├── data/                     ← banco de dados local (não versionado)
├── requirements.txt
└── .streamlit/
    └── secrets.toml.example
```

---

## Tecnologias

- [Streamlit](https://streamlit.io) — interface web
- [pypdf](https://pypdf.readthedocs.io) — leitura de PDFs
- [pandas](https://pandas.pydata.org) — manipulação de dados
- [SQLite](https://sqlite.org) — banco de dados local
- [Resend](https://resend.com) — envio de e-mail (opcional)
- [yfinance](https://github.com/ranaroussi/yfinance) — cotações

---

## Aviso legal

Este aplicativo é uma ferramenta de **apoio** à declaração do IRPF. Os dados gerados devem ser conferidos pelo contribuinte. O autor não se responsabiliza por eventuais erros na declaração.

---

## Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.
