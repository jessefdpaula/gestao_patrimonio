"""
Envio de e-mail via Resend.com (sem SMTP, sem senha).
Configuração em .streamlit/secrets.toml:

    [email]
    resend_api_key = "re_xxxxxxxxxxxx"
    from_address   = "onboarding@resend.dev"   # ou seu domínio verificado
    from_name      = "Gestão de Patrimônio"
    owner_email    = "seuemail@gmail.com"
"""

import zipfile
import io
import base64
from pathlib import Path
from datetime import datetime

try:
    import resend
except ImportError:
    resend = None

# Pastas/extensões excluídas do ZIP
_EXCLUIR_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env",
    "node_modules", ".streamlit",
}
_EXCLUIR_EXT = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}


def _criar_zip(raiz: Path) -> bytes:
    """Empacota o projeto em ZIP (em memória), excluindo arquivos desnecessários."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for caminho in sorted(raiz.rglob("*")):
            if any(parte in _EXCLUIR_DIRS for parte in caminho.parts):
                continue
            if caminho.is_dir():
                continue
            if caminho.suffix.lower() in _EXCLUIR_EXT:
                continue
            zf.write(caminho, caminho.relative_to(raiz.parent))
    return buf.getvalue()


def _html_email(nome: str) -> str:
    return f"""
<html>
<body style="font-family:'Segoe UI',Arial,sans-serif;background:#f8fafc;padding:32px;">
  <div style="max-width:560px;margin:auto;background:#fff;border-radius:12px;
              padding:32px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
    <h2 style="color:#1e3a5f;margin-bottom:4px;">📈 Gestão de Patrimônio</h2>
    <p style="color:#475569;">Olá, <strong>{nome}</strong>!</p>
    <p style="color:#475569;">
      Segue em anexo o código-fonte completo do app <strong>Gestão de Patrimônio</strong>.
    </p>
    <p style="color:#475569;"><strong>Como rodar localmente:</strong></p>
    <ol style="color:#475569;line-height:1.9;">
      <li>Instale <strong>Python 3.10+</strong></li>
      <li>
        No terminal, dentro da pasta extraída:<br>
        <code style="background:#f1f5f9;padding:2px 8px;border-radius:4px;">
          pip install -r requirements.txt
        </code>
      </li>
      <li>
        <code style="background:#f1f5f9;padding:2px 8px;border-radius:4px;">
          streamlit run app.py
        </code>
      </li>
    </ol>
    <p style="color:#94a3b8;font-size:0.83rem;margin-top:24px;">
      Enviado automaticamente em {datetime.now().strftime("%d/%m/%Y às %H:%M")}
    </p>
  </div>
</body>
</html>
""".strip()


def enviar_copia(nome: str, email_destino: str, secrets) -> tuple[bool, str]:
    """
    Envia o ZIP do app para `email_destino` via Resend.
    Retorna (sucesso: bool, mensagem: str).
    """
    if resend is None:
        return False, "Pacote 'resend' não instalado. Execute: pip install resend"

    try:
        cfg = secrets["email"]
        resend.api_key = cfg["resend_api_key"]
        from_address   = cfg.get("from_address", "onboarding@resend.dev")
        from_name      = cfg.get("from_name", "Gestão de Patrimônio")
        owner_email    = cfg.get("owner_email", "")
    except KeyError as e:
        return False, f"Chave ausente em secrets.toml: {e}"

    # Gera o ZIP
    raiz = Path(__file__).parent.parent
    zip_bytes = _criar_zip(raiz)
    zip_b64   = base64.b64encode(zip_bytes).decode()

    # ── E-mail para o solicitante ─────────────────────────────────────────────
    try:
        resend.Emails.send({
            "from":    f"{from_name} <{from_address}>",
            "to":      [email_destino],
            "subject": "📈 Gestão de Patrimônio — sua cópia do app",
            "html":    _html_email(nome),
            "attachments": [{
                "filename": "patrimonio_app.zip",
                "content":  zip_b64,
            }],
        })
    except Exception as e:
        return False, f"Erro ao enviar e-mail ao solicitante: {e}"

    # ── Notificação para o dono (sem ZIP) ─────────────────────────────────────
    if owner_email and owner_email != email_destino:
        try:
            resend.Emails.send({
                "from":    f"{from_name} <{from_address}>",
                "to":      [owner_email],
                "subject": f"[Patrimônio App] Nova solicitação — {nome}",
                "html":    f"<p><b>Nome:</b> {nome}<br><b>E-mail:</b> {email_destino}<br>"
                           f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>",
            })
        except Exception:
            pass  # falha na notificação não bloqueia o envio principal

    return True, "E-mail enviado com sucesso!"
