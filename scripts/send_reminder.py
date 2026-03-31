import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_gc():
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

def main():
    sheet_name  = os.environ["SHEET_NAME"]
    gmail_user  = os.environ["GMAIL_USER"]
    gmail_pass  = os.environ["GMAIL_PASSWORD"]
    app_url     = os.environ["APP_URL"]

    gc = get_gc()
    ss = gc.open(sheet_name)

    # Carrega membros
    try:
        members_ws = ss.worksheet("Membros")
        members = members_ws.get_all_records()
    except Exception as e:
        print(f"Erro ao carregar membros: {e}")
        return

    if not members:
        print("Nenhum membro cadastrado.")
        return

    # Carrega dailies de hoje
    today_str = date.today().strftime("%d/%m/%Y")
    try:
        daily_ws = ss.worksheet("Daily")
        dailies  = daily_ws.get_all_records()
    except Exception:
        dailies = []

    filled = {r["nome"] for r in dailies if r.get("data") == today_str}

    missing = [m for m in members if m["nome"] not in filled]
    emails  = [m["email"] for m in missing if str(m.get("email", "")).strip()]

    if not emails:
        print("Todos preencheram ou nenhum e-mail cadastrado.")
        return

    print(f"Enviando lembrete para: {emails}")

    for email in emails:
        try:
            msg = MIMEMultipart()
            msg["From"]    = gmail_user
            msg["To"]      = email
            msg["Subject"] = "Lembrete: Preencha sua Daily de hoje!"
            body = (
                f"Olá!\n\n"
                f"Ainda não identificamos seu preenchimento da daily de hoje ({today_str}).\n\n"
                f"Acesse agora e leva menos de 2 minutos:\n{app_url}\n\n"
                f"Equipe Imersa"
            )
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_pass)
                server.send_message(msg)
            print(f"  ✓ Enviado para {email}")
        except Exception as e:
            print(f"  ✗ Erro ao enviar para {email}: {e}")

if __name__ == "__main__":
    main()
