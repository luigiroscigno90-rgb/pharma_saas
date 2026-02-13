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
from streamlit_mic_recorder import mic_recorder
import io
import random

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI Suite", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f4f6f9;}
    div[data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    .stMetric {background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    h1, h2, h3 {color: #2c3e50;}
    .dataframe {font-size: 14px !important;}
    button[kind="secondary"] {border-radius: 50px; border: 1px solid #ddd; height: 3rem;}
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTH SYSTEM ---
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
        return None

# --- 4. DATA & SCENARIOS (ROGUE EDITION) ---
SCENARIOS = {
    "Dolore Articolare (Anziano)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Maria, 70 anni.", 
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria. Hai male al ginocchio. Vuoi solo il Voltaren. Accetti il collagene SOLO se spiegano che la crema spegne il dolore oggi, ma il collagene ripara la cartilagine per domani.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai dimenticato il bancomat a casa, hai solo 15 euro in contanti.",
            "IMPREVISTO: Sei allergica all'Aspirina/FANS.",
            "IMPREVISTO: Tua figlia ti ha detto che il collagene fa ingrassare."
        ]
    },
    "Cervicale e Stress": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Marco, 45 anni.", 
        "obiettivo": "Vendere: Cerotti + Magnesio.",
        "sys_prompt": "Sei Marco. Collo bloccato. Vuoi pastiglia forte. Rifiuti magnesio. Accetti SOLO se spiegano che scioglie la contrattura muscolare.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai la pelle molto sensibile, i cerotti ti fanno allergia.",
            "IMPREVISTO: Sei diabetico. Chiedi se il Magnesio contiene zucchero."
        ]
    },
    "Mal di Testa (Donna)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Chiara, 30 anni.", 
        "obiettivo": "Vendere: Ibuprofene + Coadiuvante.",
        "sys_prompt": "Sei Chiara. Cerchio alla testa. Vuoi il solito farmaco. Accetti integratore solo per stanchezza mentale.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sospetti di essere incinta (niente FANS).",
            "IMPREVISTO: La caffeina ti fa venire la tachicardia."
        ]
    },
    "Tosse Secca (Fumatore)": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Roberto, 50 anni.", 
        "obiettivo": "Vendere: Sciroppo + Spray.",
        "sys_prompt": "Sei Roberto. Tosse fumo. Rifiuti spray. Accetti solo se protegge dal catrame.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sei diabetico, niente zuccheri.",
            "IMPREVISTO: Dì che tua moglie ti stressa per smettere di fumare."
        ]
    },
    "Influenza (Prevenzione)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Giovanna, 75 anni.", 
        "obiettivo": "Vendere: Tachipirina + Vit C.",
        "sys_prompt": "Sei Giovanna. Paura influenza. Compri Tachipirina. Accetti prevenzione solo per difese basse.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Non riesci a deglutire le pastiglie grosse.",
            "IMPREVISTO: Prendi il Coumadin (anticoagulante)."
        ]
    },
    "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Giuseppe, 55 anni.", 
        "obiettivo": "Vendere: Antiacido + Probiotici.",
        "sys_prompt": "Sei Giuseppe. Bruciore. Compri probiotici SOLO se spiegano che riparano la mucosa.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Soffri di pressione alta (no sodio).",
            "IMPREVISTO: Dì che i fermenti lattici ti gonfiano la pancia."
        ]
    },
    "Gonfiore Addominale": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Simona, 35 anni.", 
        "obiettivo": "Vendere: Carbone + Enzimi.",
        "sys_prompt": "Sei Simona. Gonfia. Rifiuti enzimi. Accetti SOLO se spiegano differenza col carbone.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Ti serve effetto immediato per una cena stasera."
        ]
    },
    "Terapia Antibiotica": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Laura, 40 anni.", 
        "obiettivo": "Vendere: Antibiotico + Fermenti.",
        "sys_prompt": "Sei Laura. Ricetta antibiotico. Rifiuti fermenti. Accetti SOLO se spiegano rischio diarrea.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Il bambino vomita le fialette.",
            "IMPREVISTO: Chiedi se va preso a stomaco pieno o vuoto."
        ]
    },
    "Insonnia e Stress": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Giulia, 42 anni.", 
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia. Dormi male. Scettica sul naturale.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Ti svegli sempre alle 3 di notte (serve Retard)."
        ]
    },
    "Anti-Age Viso": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Elena, 55 anni.", 
        "obiettivo": "Vendere: Crema + Siero.",
        "sys_prompt": "Sei Elena. Vuoi crema. Rifiuti siero. Accetti solo se veicola.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Pelle mista che si lucida."
        ]
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
    categories = ['Empatia', 'Tecnica', 'Chiusura', 'Ascolto', 'Gestione Imprevisto']
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='Tu'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, margin=dict(t=20, b=20, l=40, r=40))
    return fig

# --- 6. DASHBOARD TITOLARE (ADMIN) ---
def render_admin_dashboard():
    st.title("📊 PharmaBoss Dashboard")
    if not os.path.exists(KPI_FILE):
        st.warning("Nessun dato registrato. Fai fare la prima simulazione ai tuoi dipendenti!")
        return

    df = pd.read_csv(KPI_FILE)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fatturato Potenziale", f"€ {df['Revenue'].sum()}")
    col2.metric("Media Voto Team", f"{int(df['Score'].mean())}/100")
    col3.metric("Simulazioni Totali", len(df))
    col4.metric("Farmacisti Attivi", df['User'].nunique())
    
    st.divider()
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🏆 Top Performer")
        leaderboard = df.groupby('User').agg({'Score': 'mean', 'Revenue': 'sum', 'Scenario': 'count'}).reset_index()
        leaderboard = leaderboard.sort_values(by='Fatturato Totale', ascending=False)
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
    with c2:
        st.subheader("📉 Aree Critiche")
        weakness = df.groupby('Scenario')['Score'].mean().sort_values()
        fig_bar = px.bar(weakness, x='Score', y=weakness.index, orientation='h', color='Score', title="Media Voto per Caso")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()
    st.subheader("🔎 Analisi Singolo Dipendente")
    selected_emp = st.selectbox("Seleziona Farmacista:", df['User'].unique())
    emp_df = df[df['User'] == selected_emp]
    fig_line = px.line(emp_df, x=emp_df.index, y='Score', markers=True, title=f"Trend Miglioramento: {selected_emp}")
    st.plotly_chart(fig_line, use_container_width=True)
    st.write("🛑 **Ultimi Errori Rilevati:**")
    st.table(emp_df[['Scenario', 'Score']].tail(5))

# --- 7. SIDEBAR LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

with st.sidebar:
    st.title("PharmaFlow 🎲")
    
    if st.session_state.logged_in:
        user = st.session_state.user_info
        st.write(f"**{user['avatar']} {user['name']}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.divider()
    
    admin_mode = False
    if st.checkbox("🔐 Area Titolare"):
        pwd = st.text_input("Master Password", type="password")
        if pwd == ADMIN_PASS:
            admin_mode = True
            st.success("Accesso Admin Garantito")
        elif pwd:
            st.error("Password Errata")

# --- 8. ROUTING ---

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
                    st.session_state.logged_in = True
                    st.session_state.user_info = data
                    st.rerun()
                else: 
                    st.error("Errore login")
    with tab2:
        with st.form("reg"):
            nu = st.text_input("Nuovo User"); np = st.text_input("Nuova Pass", type="password")
            fn = st.text_input("Nome Completo"); ge = st.selectbox("Sesso", ["Uomo", "Donna"])
            if st.form_submit_button("Crea"):
                if save_user(nu, np, fn, ge): 
                    st.success("Creato! Vai su Accedi.")
                else: 
                    st.error("Esiste già")
    st.stop()

# CASO C: PHARMACIST TRAINING MODE
sel_scenario = st.sidebar.selectbox("Training:", list(SCENARIOS.keys()))
hard = st.sidebar.toggle("🔥 Hard Mode")

# --- GESTIONE ROGUE MODE (Imprevisti) ---
if "current_scenario" not in st.session_state: st.session_state.current_scenario = ""
if "current_twist" not in st.session_state: st.session_state.current_twist = ""

trigger_reset = st.sidebar.button("🎲 Nuova Simulazione")

if trigger_reset or st.session_state.current_scenario != sel_scenario:
    st.session_state.messages = []
    st.session_state.current_scenario = sel_scenario
    # Pesca un imprevisto casuale
    possible_twists = SCENARIOS[sel_scenario].get('twists', ["Nessun imprevisto."])
    st.session_state.current_twist = random.choice(possible_twists)
    st.rerun()

curr = SCENARIOS[sel_scenario]
st.header(f"Simulazione: {sel_scenario}")
st.markdown(f"**Obiettivo:** {curr['obiettivo']}")

# (Opzionale: Debug Twist)
# st.caption(f"Debug Twist: {st.session_state.current_twist}")

if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages: 
    with st.chat_message(m["role"]): st.write(m["content"])

if st.button("💡 Suggerimento"):
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    h = get_ai_response([{"role":"system","content":f"Tutor per: {curr['obiettivo']}. Suggerisci frase breve."},{"role":"user","content":hist}])
    st.info(f"Tip: {h}")

st.divider()
col_mic, col_text = st.columns([1, 8])
final_input = None

with col_mic:
    audio_data = mic_recorder(start_prompt="🎤", stop_prompt="⏹️", key='recorder', format="wav", use_container_width=True)

with col_text:
    text_input = st.chat_input("Scrivi qui la tua risposta...")

if audio_data:
    with st.spinner("Trascrizione vocale..."):
        text_from_audio = transcribe_audio(audio_data['bytes'])
        if text_from_audio: final_input = text_from_audio
elif text_input:
    final_input = text_input

if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"): st.write(final_input)
    
    with st.spinner("..."):
        # INIETTA L'IMPREVISTO NEL PROMPT
        twist_prompt = f" IMPORTANTE: Per questa sessione c'è un imprevisto specifico: {st.session_state.current_twist}. Reagisci di conseguenza."
        sys = curr['sys_prompt'] + (" Sii scontroso." if hard else "") + twist_prompt
        
        ai_msg = get_ai_response([{"role":"system","content":sys}] + st.session_state.messages)
        asyncio.run(text_to_speech(ai_msg, curr['voice']))
    
    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
    with st.chat_message("assistant"): st.write(ai_msg); autoplay_audio("temp_audio.mp3")

if len(st.session_state.messages)>2 and st.button("🏁 Valuta", type="primary", use_container_width=True):
    with st.spinner("Analisi..."):
        hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        prompt = f"Analisi {sel_scenario}. Imprevisto affrontato: {st.session_state.current_twist}. JSON: {{'score_empatia':1-10, 'score_tecnica':1-10, 'score_chiusura':1-10, 'score_ascolto':1-10, 'score_obiezioni':1-10, 'totale':0-100, 'revenue':euro, 'feedback_main':'txt', 'mistake':'txt', 'correction':'txt'}}\nCHAT:\n{hist}"
        res = get_ai_response([{"role":"user","content":prompt}], json_mode=True)
        try:
            d = json.loads(res)
            st.balloons()
            t1, t2 = st.tabs(["Performance", "Dettagli"])
            with t1: 
                c1,c2=st.columns(2)
                c1.plotly_chart(plot_radar([d['score_empatia'],d['score_tecnica'],d['score_chiusura'],d['score_ascolto'],d['score_obiezioni']]))
                c2.metric("Voto", f"{d['totale']}/100"); c2.metric("Fatturato", f"€ {d['revenue']}")
                if st.session_state.current_twist != "Nessun imprevisto.":
                    st.info(f"Imprevisto Gestito: {st.session_state.current_twist}")
            with t2: st.error(d['mistake']); st.success(d['correction'])
            
            row = {"Date":datetime.now().strftime("%Y-%m-%d %H:%M"), "User": st.session_state.user_info['name'], "Scenario": sel_scenario, "Score": d['totale'], "Revenue": d['revenue']}
            try: pd.read_csv(KPI_FILE)._append(row, ignore_index=True).to_csv(KPI_FILE, index=False)
            except: pd.DataFrame([row]).to_csv(KPI_FILE, index=False)
        except: st.error("Errore report")