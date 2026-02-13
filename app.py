import os
import streamlit as st
from groq import Groq
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts
import plotly.graph_objects as go
import plotly.express as px
import hashlib
from streamlit_mic_recorder import mic_recorder # NUOVO: Libreria per il microfono
import io # NUOVO: Per gestire i file audio in memoria

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI Suite", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f4f6f9;}
    div[data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    .stMetric {background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    h1, h2, h3 {color: #2c3e50;}
    /* Tabella Admin più leggibile */
    .dataframe {font-size: 14px !important;}
    /* Stile bottone microfono */
    button[kind="secondary"] {border-radius: 50px; border: 1px solid #ddd; height: 3rem;}
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTH SYSTEM (Password Hashing) ---
DB_FILE = "users_db.json"
KPI_FILE = "kpi_db.csv"
ADMIN_PASS = "admin123"

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def load_users():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r") as f: return json.load(f)

def save_user(username, password, name, gender):
    users = load_users()
    if username in users: return False
    users[username] = {
        "password": make_hashes(password),
        "name": name, 
        "gender": gender,
        "avatar": "👨‍⚕️" if gender == "Uomo" else "👩‍⚕️"
    }
    with open(DB_FILE, "w") as f: json.dump(users, f)
    return True

def login_user(username, password):
    users = load_users()
    if username in users and check_hashes(password, users[username]['password']):
        return users[username]
    return None

# --- 3. MOTORE AI (GROQ) ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("⚠️ GROQ_API_KEY mancante!")
    st.stop()

def get_ai_response(messages, temp=0.7, json_mode=False):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temp,
            max_tokens=1024,
            response_format={"type": "json_object"} if json_mode else None
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Errore AI: {e}"

# NUOVO: Funzione per trascrivere audio con Groq Whisper
def transcribe_audio(audio_bytes):
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav" 
        transcription = client.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model="whisper-large-v3",
            response_format="text",
            language="it"
        )
        return transcription
    except Exception as e:
        st.error(f"Errore Trascrizione: {e}")
        return None

# --- 4. DATA & SCENARIOS ---
SCENARIOS = {
    "Dolore Articolare": {
        "voice": "it-IT-ElsaNeural", "persona": "Maria, 68 anni.", 
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria, 68 anni. Diffidente. Hai male al ginocchio. Vuoi solo la crema. Accetti il collagene SOLO se il farmacista ti spiega che la crema toglie il dolore oggi, ma il collagene ripara la cartilagine per il futuro. Rispondi in max 20 parole."
    },
    "Tosse Fumatore": {
        "voice": "it-IT-DiegoNeural", "persona": "Luca, 35 anni.", 
        "obiettivo": "Vendere: Sciroppo + Spray Gola.",
        "sys_prompt": "Sei Luca, 35 anni, fumatore. Hai fretta. Accetti lo spray SOLO se ti dicono che crea una barriera protettiva contro il fumo. Sii sbrigativo. Rispondi in max 15 parole."
    },
    "Insonnia Stress": {
        "voice": "it-IT-ElsaNeural", "persona": "Giulia, 42 anni.", 
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia, manager stressata. Vuoi farmaci forti. Accetti integratori SOLO se ti spiegano l'azione rilassante sul sistema nervoso. Sii scettica."
    },
     "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural", "persona": "Marco, 50 anni.", 
        "obiettivo": "Vendere: Antiacido + Probiotici.",
        "sys_prompt": "Sei Marco. Mangi male. Vuoi solo tamponare il bruciore. Compri i probiotici solo se ti spiegano che riequilibrano la digestione."
    }
}

# --- 5. FUNZIONI UTILI ---
async def text_to_speech(text, voice_id):
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save("temp_audio.mp3")
        return True
    except: return False

def autoplay_audio(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""<audio controls autoplay style="width: 100%; margin-top: 5px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
        st.markdown(md, unsafe_allow_html=True)

def plot_radar(values):
    categories = ['Empatia', 'Tecnica', 'Chiusura', 'Ascolto', 'Obiezioni']
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='Tu'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, margin=dict(t=20, b=20, l=40, r=40))
    return fig

# --- 6. DASHBOARD TITOLARE (ADMIN) ---
def render_admin_dashboard():
    st.title("📊 PharmaBoss Dashboard")
    st.markdown("Monitoraggio performance e ROI della formazione.")
    
    if not os.path.exists(KPI_FILE):
        st.warning("Nessun dato registrato. Fai fare la prima simulazione ai tuoi dipendenti!")
        return

    df = pd.read_csv(KPI_FILE)
    
    # 1. KPI GENERALI
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fatturato Potenziale", f"€ {df['Revenue'].sum()}")
    col2.metric("Media Voto Team", f"{int(df['Score'].mean())}/100")
    col3.metric("Simulazioni Totali", len(df))
    col4.metric("Farmacisti Attivi", df['User'].nunique())
    
    st.divider()
    
    # 2. CLASSIFICA (LEADERBOARD)
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("🏆 Top Performer")
        leaderboard = df.groupby('User').agg({'Score': 'mean', 'Revenue': 'sum', 'Scenario': 'count'}).reset_index()
        leaderboard.columns = ['Farmacista', 'Voto Medio', 'Fatturato Totale', 'N. Sessioni']
        leaderboard = leaderboard.sort_values(by='Fatturato Totale', ascending=False)
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
    with c2:
        st.subheader("📉 Aree Critiche")
        weakness = df.groupby('Scenario')['Score'].mean().sort_values()
        fig_bar = px.bar(weakness, x='Score', y=weakness.index, orientation='h', 
                         color='Score', color_continuous_scale='RdYlGn', title="Media Voto per Caso")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # 3. ANALISI SINGOLA (DRILL DOWN)
    st.subheader("🔎 Analisi Singolo Dipendente")
    selected_emp = st.selectbox("Seleziona Farmacista:", df['User'].unique())
    
    emp_df = df[df['User'] == selected_emp]
    
    # Grafico Andamento nel Tempo
    fig_line = px.line(emp_df, x=emp_df.index, y='Score', markers=True, title=f"Trend Miglioramento: {selected_emp}")
    st.plotly_chart(fig_line, use_container_width=True)
    
    # Ultimi Feedback negativi
    st.write("🛑 **Ultimi Errori Rilevati:**")
    st.table(emp_df[['Scenario', 'Score']].tail(5))

# --- 7. SIDEBAR LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

with st.sidebar:
    st.title("PharmaFlow")
    
    # LOGIN/LOGOUT
    if st.session_state.logged_in:
        user = st.session_state.user_info
        st.write(f"**{user['avatar']} {user['name']}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.divider()
    
    # ADMIN TOGGLE
    admin_mode = False
    if st.checkbox("🔐 Area Titolare"):
        pwd = st.text_input("Master Password", type="password")
        if pwd == ADMIN_PASS:
            admin_mode = True
            st.success("Accesso Admin Garantito")
        elif pwd:
            st.error("Password Errata")

# --- 8. ROUTING ---

# CASO A: ADMIN MODE ATTIVA
if admin_mode:
    render_admin_dashboard()
    st.stop() 

# CASO B: LOGIN SCREEN
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔑 Accedi", "📝 Registra Farmacista"])
    with tab1:
        with st.form("login"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Entra"):
                data = login_user(u, p)
                if data: 
                    st.session_state.logged_in = True; st.session_state.user_info = data; st.rerun()
                else: st.error("Errore login")
    with tab2:
        with st.form("reg"):
            nu = st.text_input("Nuovo User"); np = st.text_input("Nuova Pass", type="password")
            fn = st.text_input("Nome Completo"); ge = st.selectbox("Sesso", ["Uomo", "Donna"])
            if st.form_submit_button("Crea"):
                if save_user(nu, np, fn, ge): st.success("Creato! Vai su Accedi."); 
                else: st.error("User esiste già")
    st.stop()

# CASO C: PHARMACIST TRAINING MODE
sel_scenario = st.sidebar.selectbox("Training:", list(SCENARIOS.keys()))
hard = st.sidebar.toggle("🔥 Hard Mode")
if st.sidebar.button("Reset Chat"): st.session_state.messages = []; st.rerun()

curr = SCENARIOS[sel_scenario]
st.header(f"Simulazione: {sel_scenario}")
st.markdown(f"**Obiettivo:** {curr['obiettivo']}")

if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages: 
    with st.chat_message(m["role"]): st.write(m["content"])

# Tutor
if st.button("💡 Suggerimento"):
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    h = get_ai_response([{"role":"system","content":f"Tutor per: {curr['obiettivo']}. Suggerisci frase breve."},{"role":"user","content":hist}])
    st.info(f"Tip: {h}")

# --- INPUT AREA: VOCE O TESTO (MODIFICATO) ---
st.divider()
col_mic, col_text = st.columns([1, 8])

final_input = None

with col_mic:
    # Componente Microfono
    audio_data = mic_recorder(
        start_prompt="🎤",
        stop_prompt="⏹️",
        key='recorder',
        format="wav",
        use_container_width=True
    )

with col_text:
    text_input = st.chat_input("Scrivi qui la tua risposta...")

# LOGICA DI GESTIONE INPUT
if audio_data:
    with st.spinner("Trascrizione vocale..."):
        text_from_audio = transcribe_audio(audio_data['bytes'])
        if text_from_audio:
            final_input = text_from_audio
elif text_input:
    final_input = text_input

# --- ESECUZIONE CHAT ---
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"): st.write(final_input)
    
    with st.spinner("..."):
        sys = curr['sys_prompt'] + (" Sii scontroso." if hard else "")
        ai_msg = get_ai_response([{"role":"system","content":sys}] + st.session_state.messages)
        asyncio.run(text_to_speech(ai_msg, curr['voice']))
    
    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
    with st.chat_message("assistant"): st.write(ai_msg); autoplay_audio("temp_audio.mp3")

# Evaluation
if len(st.session_state.messages)>2 and st.button("🏁 Valuta", type="primary", use_container_width=True):
    with st.spinner("Analisi..."):
        hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        prompt = f"Analisi {sel_scenario}. JSON: {{'score_empatia':1-10, 'score_tecnica':1-10, 'score_chiusura':1-10, 'score_ascolto':1-10, 'score_obiezioni':1-10, 'totale':0-100, 'revenue':euro, 'feedback_main':'txt', 'mistake':'txt', 'correction':'txt'}}\nCHAT:\n{hist}"
        res = get_ai_response([{"role":"user","content":prompt}], json_mode=True)
        try:
            d = json.loads(res)
            st.balloons()
            t1, t2 = st.tabs(["Performance", "Dettagli"])
            with t1: 
                c1,c2=st.columns(2)
                c1.plotly_chart(plot_radar([d['score_empatia'],d['score_tecnica'],d['score_chiusura'],d['score_ascolto'],d['score_obiezioni']]))
                c2.metric("Voto", f"{d['totale']}/100"); c2.metric("Fatturato", f"€ {d['revenue']}")
            with t2: st.error(d['mistake']); st.success(d['correction'])
            
            # Save KPI
            row = {"Date":datetime.now().strftime("%Y-%m-%d %H:%M"), "User": st.session_state.user_info['name'], "Scenario": sel_scenario, "Score": d['totale'], "Revenue": d['revenue']}
            try: pd.read_csv(KPI_FILE)._append(row, ignore_index=True).to_csv(KPI_FILE, index=False)
            except: pd.DataFrame([row]).to_csv(KPI_FILE, index=False)
        except: st.error("Errore report")