import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

ADMIN_PASSWORD = "Imersa-daily"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─── GOOGLE SHEETS ─────────────────────────────────────────────────────────────

@st.cache_resource
def get_gc():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_spreadsheet():
    return get_gc().open(st.secrets["sheet_name"])

def get_daily_ws():
    ss = get_spreadsheet()
    try:
        return ss.worksheet("Daily")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet("Daily", 2000, 8)
        ws.append_row(["timestamp", "data", "nome", "funcao",
                        "feito_hoje", "bloqueios", "dificuldades", "amanha"])
        return ws

def get_members_ws():
    ss = get_spreadsheet()
    try:
        return ss.worksheet("Membros")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet("Membros", 100, 3)
        ws.append_row(["nome", "funcao", "email"])
        return ws

@st.cache_data(ttl=60)
def load_dailies():
    data = get_daily_ws().get_all_records()
    if not data:
        return pd.DataFrame(columns=["timestamp", "data", "nome", "funcao",
                                      "feito_hoje", "bloqueios", "dificuldades", "amanha"])
    return pd.DataFrame(data)

@st.cache_data(ttl=60)
def load_members():
    data = get_members_ws().get_all_records()
    if not data:
        return pd.DataFrame(columns=["nome", "funcao", "email"])
    return pd.DataFrame(data)

def submit_daily(nome, funcao, feito_hoje, bloqueios, dificuldades, amanha):
    get_daily_ws().append_row([
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        date.today().strftime("%d/%m/%Y"),
        nome, funcao, feito_hoje, bloqueios, dificuldades, amanha
    ])
    load_dailies.clear()

def add_member(nome, funcao, email):
    get_members_ws().append_row([nome, funcao, email])
    load_members.clear()

def remove_member(nome):
    ws = get_members_ws()
    cell = ws.find(nome)
    if cell:
        ws.delete_rows(cell.row)
    load_members.clear()

def delete_daily_row(timestamp: str, nome: str):
    ws = get_daily_ws()
    records = ws.get_all_records()
    for i, row in enumerate(records, start=2):  # row 1 = header
        if str(row.get("timestamp", "")) == timestamp and str(row.get("nome", "")) == nome:
            ws.delete_rows(i)
            break
    load_dailies.clear()

# ─── EMAIL ─────────────────────────────────────────────────────────────────────

def send_reminder_emails(emails_missing: list, app_url: str):
    gmail_user = st.secrets["gmail_user"]
    gmail_password = st.secrets["gmail_password"]
    erros = []
    for email in emails_missing:
        try:
            msg = MIMEMultipart()
            msg["From"] = gmail_user
            msg["To"] = email
            msg["Subject"] = "Lembrete: Preencha sua Daily de hoje!"
            body = (
                f"Olá!\n\n"
                f"Este é um lembrete automático da Imersa.\n"
                f"Você ainda não preencheu a daily de hoje.\n\n"
                f"Acesse agora: {app_url}\n\n"
                f"Equipe Imersa"
            )
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_password)
                server.send_message(msg)
        except Exception as e:
            erros.append(f"{email}: {e}")
    return erros

# ─── ESTILOS ───────────────────────────────────────────────────────────────────

DARK_CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #0f0f0f; }
[data-testid="stSidebar"] { background: #1a1a1a; }
.block-container { padding-top: 2rem; }
.daily-card {
    background: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 18px 22px;
    margin-bottom: 14px;
}
.daily-card-name {
    font-size: 17px;
    font-weight: 700;
    color: #e2e8f0;
    margin-bottom: 2px;
}
.daily-card-role {
    font-size: 12px;
    color: #888;
    margin-bottom: 14px;
}
.daily-section-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #666;
    margin-bottom: 4px;
}
.daily-section-value {
    font-size: 14px;
    color: #d4d4d4;
    margin-bottom: 12px;
    white-space: pre-wrap;
}
.badge-ok   { background:#14532d; color:#4ade80; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:600; }
.badge-pend { background:#3b0f0f; color:#f87171; border-radius:6px; padding:3px 10px; font-size:12px; font-weight:600; }
</style>
"""

# ─── PÁGINA: FORMULÁRIO ────────────────────────────────────────────────────────

def page_form():
    st.markdown(DARK_CSS, unsafe_allow_html=True)
    st.title("📋 Daily Imersa")
    st.caption(f"Hoje é {date.today().strftime('%d/%m/%Y')}")

    df_members = load_members()
    if df_members.empty:
        st.warning("Nenhum membro cadastrado. Peça ao administrador para cadastrar os membros.")
        st.stop()

    nomes = ["Selecione seu nome..."] + sorted(df_members["nome"].tolist())

    with st.form("daily_form", clear_on_submit=True):
        nome = st.selectbox("Seu nome", nomes)

        funcao = ""
        if nome != "Selecione seu nome...":
            row = df_members[df_members["nome"] == nome]
            if not row.empty:
                funcao = row.iloc[0]["funcao"]
        st.text_input("Função", value=funcao, disabled=True)

        st.divider()

        feito_hoje  = st.text_area("✅ O que você fez hoje?",    height=120, placeholder="Descreva as tarefas realizadas...")
        bloqueios   = st.text_area("🚧 O que ficou bloqueado?",  height=100, placeholder="Impedimentos ou bloqueios...")
        dificuldades= st.text_area("⚠️ Dificuldades do dia",     height=100, placeholder="Dificuldades enfrentadas...")
        amanha      = st.text_area("📅 O que fica para amanhã?", height=100, placeholder="Tarefas do próximo dia...")

        submitted = st.form_submit_button("Enviar Daily", use_container_width=True, type="primary")

    if submitted:
        if nome == "Selecione seu nome...":
            st.error("Selecione seu nome.")
        elif not feito_hoje.strip():
            st.error("Preencha o campo 'O que você fez hoje'.")
        else:
            df_daily = load_dailies()
            today_str = date.today().strftime("%d/%m/%Y")
            ja_preencheu = (
                not df_daily.empty and
                not df_daily[(df_daily["nome"] == nome) & (df_daily["data"] == today_str)].empty
            )
            if ja_preencheu:
                st.warning("Você já preencheu a daily hoje!")
            else:
                submit_daily(nome, funcao, feito_hoje, bloqueios, dificuldades, amanha)
                st.success("Daily enviada com sucesso! 🎉")
                st.balloons()

# ─── PÁGINA: ADMIN ─────────────────────────────────────────────────────────────

def page_admin():
    st.markdown(DARK_CSS, unsafe_allow_html=True)

    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

    if not st.session_state.admin_auth:
        st.title("🔒 Admin Daily")
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            senha = st.text_input("Senha de acesso", type="password")
            if st.button("Entrar", use_container_width=True):
                if senha == ADMIN_PASSWORD:
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
        st.stop()

    st.title("📊 Central de Dailies")

    if st.sidebar.button("🔄 Atualizar dados"):
        load_dailies.clear()
        load_members.clear()
        st.rerun()

    if st.sidebar.button("🚪 Sair"):
        st.session_state.admin_auth = False
        st.rerun()

    df_daily   = load_dailies()
    df_members = load_members()

    tab1, tab2, tab3 = st.tabs(["📅 Daily do dia", "📁 Histórico", "👥 Equipe"])

    # ── TAB 1: Daily do dia ────────────────────────────────────────────────────
    with tab1:
        col_date, col_btn = st.columns([2, 1])
        with col_date:
            sel_date = st.date_input("Data", value=date.today(), key="sel_date")
        sel_str = sel_date.strftime("%d/%m/%Y")

        df_today = (
            df_daily[df_daily["data"] == sel_str].copy()
            if not df_daily.empty else pd.DataFrame()
        )
        all_members = df_members["nome"].tolist() if not df_members.empty else []
        filled      = df_today["nome"].tolist() if not df_today.empty else []
        missing     = [m for m in all_members if m not in filled]

        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📧 Enviar lembrete", use_container_width=True):
                if missing:
                    emails = (
                        df_members[df_members["nome"].isin(missing)]["email"]
                        .dropna().tolist()
                    )
                    emails = [e for e in emails if str(e).strip()]
                    if emails:
                        app_url = st.secrets.get("app_url", "seu-link-aqui")
                        erros = send_reminder_emails(emails, app_url)
                        if erros:
                            st.error("Erros: " + "; ".join(erros))
                        else:
                            st.success(f"Lembrete enviado para {len(emails)} pessoa(s)!")
                    else:
                        st.warning("Nenhum e-mail cadastrado para os pendentes.")
                else:
                    st.info("Todos já preencheram!")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total da equipe", len(all_members))
        c2.metric("Preencheram", len(filled))
        c3.metric("Pendentes", len(missing))

        # Status badges
        st.markdown("#### Status da equipe")
        badges = ""
        for m in sorted(all_members):
            cls = "badge-ok" if m in filled else "badge-pend"
            badges += f'<span class="{cls}" style="margin:3px;display:inline-block">{m}</span> '
        st.markdown(badges, unsafe_allow_html=True)

        st.divider()

        if df_today.empty:
            st.info("Nenhuma daily registrada para esta data.")
        else:
            for _, row in df_today.iterrows():
                st.markdown(f"""
<div class="daily-card">
  <div class="daily-card-name">👤 {row['nome']}</div>
  <div class="daily-card-role">{row['funcao']} · {row.get('timestamp','')}</div>
  <div class="daily-section-label">✅ O que fez hoje</div>
  <div class="daily-section-value">{row['feito_hoje'] or '—'}</div>
  <div class="daily-section-label">📅 Para amanhã</div>
  <div class="daily-section-value">{row['amanha'] or '—'}</div>
  <div class="daily-section-label">🚧 Bloqueios</div>
  <div class="daily-section-value">{row['bloqueios'] or '—'}</div>
  <div class="daily-section-label">⚠️ Dificuldades</div>
  <div class="daily-section-value">{row['dificuldades'] or '—'}</div>
</div>
""", unsafe_allow_html=True)

            st.divider()
            with st.expander("🗑️ Excluir registro de teste"):
                opcoes = [
                    f"{r['nome']} — {r.get('timestamp','')}"
                    for _, r in df_today.iterrows()
                ]
                sel = st.selectbox("Selecione o registro", opcoes, key="del_sel")
                if st.button("Excluir registro selecionado", type="secondary", key="del_btn"):
                    idx = opcoes.index(sel)
                    row_del = df_today.iloc[idx]
                    delete_daily_row(str(row_del["timestamp"]), str(row_del["nome"]))
                    st.success("Registro excluído.")
                    st.rerun()

    # ── TAB 2: Histórico ───────────────────────────────────────────────────────
    with tab2:
        c1, c2, c3 = st.columns(3)
        with c1:
            nomes_opts = ["Todos"] + sorted(df_members["nome"].tolist())
            filtro_nome = st.selectbox("Pessoa", nomes_opts, key="hist_nome")
        with c2:
            meses = ["Todos"] + [
                f"{m:02d}/{datetime.now().year}" for m in range(1, 13)
            ]
            filtro_mes = st.selectbox("Mês", meses, key="hist_mes")
        with c3:
            filtro_semana = st.selectbox(
                "Semana", ["Todas", "Esta semana", "Semana passada"], key="hist_sem"
            )

        df_hist = df_daily.copy() if not df_daily.empty else pd.DataFrame()

        if not df_hist.empty:
            df_hist["data_dt"] = pd.to_datetime(df_hist["data"], format="%d/%m/%Y", errors="coerce")

            if filtro_nome != "Todos":
                df_hist = df_hist[df_hist["nome"] == filtro_nome]

            if filtro_mes != "Todos":
                mes_n, ano_n = filtro_mes.split("/")
                df_hist = df_hist[
                    (df_hist["data_dt"].dt.month == int(mes_n)) &
                    (df_hist["data_dt"].dt.year  == int(ano_n))
                ]

            if filtro_semana == "Esta semana":
                hoje = date.today()
                inicio = hoje - timedelta(days=hoje.weekday())
                df_hist = df_hist[df_hist["data_dt"].dt.date >= inicio]
            elif filtro_semana == "Semana passada":
                hoje   = date.today()
                inicio = hoje - timedelta(days=hoje.weekday() + 7)
                fim    = inicio + timedelta(days=6)
                df_hist = df_hist[
                    (df_hist["data_dt"].dt.date >= inicio) &
                    (df_hist["data_dt"].dt.date <= fim)
                ]

            df_hist = df_hist.sort_values("data_dt", ascending=False)
            df_show = df_hist[["data","nome","funcao","feito_hoje","bloqueios","dificuldades","amanha"]].rename(columns={
                "data":"Data","nome":"Nome","funcao":"Função",
                "feito_hoje":"Feito hoje","bloqueios":"Bloqueios",
                "dificuldades":"Dificuldades","amanha":"Amanhã"
            })
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado ainda.")

    # ── TAB 3: Equipe ──────────────────────────────────────────────────────────
    with tab3:
        st.subheader("Membros cadastrados")
        if not df_members.empty:
            st.dataframe(
                df_members.rename(columns={"nome":"Nome","funcao":"Função","email":"E-mail"}),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Nenhum membro cadastrado.")

        st.divider()
        st.subheader("Adicionar membro")
        with st.form("add_member"):
            c1, c2, c3 = st.columns(3)
            with c1: new_nome   = st.text_input("Nome")
            with c2: new_funcao = st.text_input("Função")
            with c3: new_email  = st.text_input("E-mail")
            if st.form_submit_button("Adicionar", type="primary"):
                if new_nome.strip() and new_funcao.strip():
                    add_member(new_nome.strip(), new_funcao.strip(), new_email.strip())
                    st.success(f"{new_nome} adicionado!")
                    st.rerun()
                else:
                    st.error("Nome e função são obrigatórios.")

        if not df_members.empty:
            st.divider()
            st.subheader("Remover membro")
            rm_nome = st.selectbox("Selecione", sorted(df_members["nome"].tolist()), key="rm_nome")
            if st.button("Remover", type="secondary"):
                remove_member(rm_nome)
                st.success(f"{rm_nome} removido.")
                st.rerun()

# ─── ROTEAMENTO ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Daily Imersa",
    layout="wide",
    page_icon="📋"
)

page = st.query_params.get("page", "form")
if page == "admin":
    page_admin()
else:
    page_form()
