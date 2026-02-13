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
import random  # <--- NUOVO: Necessario per generare casualità

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
    /* Badge per l'imprevisto (solo per debug o admin) */
    .twist-badge {background-color: #e74c3c; color: white; padding: 5px; border-radius: 5px; font-weight: bold; font-size: 0.8em;}
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTH SYSTEM ---
DB_FILE = "users_db.json"
KPI_FILE = "kpi_db.csv"
ADMIN_PASS = "admin123"

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

def load_users():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r") as f: return json.load(f)

def save_user(username, password, name, gender):
    users = load_users()
    if username in users: return False
    users[username] = {"password": make_hashes(password), "name": name, "gender": gender, "avatar": "👨‍⚕️" if gender == "Uomo" else "👩‍⚕️"}
    with open(DB_FILE, "w") as f: json.dump(users, f)
    return True

def login_user(username, password):
    users = load_users()
    if username in users and check_hashes(password, users[username]['password']): return users[username]
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
    except Exception as e: return f"Errore AI: {e}"

def transcribe_audio(audio_bytes):
    try:
        audio_file = io.BytesIO(audio_bytes); audio_file.name = "audio.wav" 
        transcription = client.audio.transcriptions.create(file=(audio_file.name, audio_file.read()), model="whisper-large-v3", response_format="text", language="it")
        return transcription
    except: return None

# --- 4. DATA & SCENARIOS (ROGUE EDITION) ---
# Ho aggiunto la lista 'twists' ad ogni scenario
SCENARIOS = {
    # --- 1. DOLORE E INFIAMMAZIONE ---
    "Dolore Articolare (Anziano)": {
        "voice": "it-IT-ElsaNeural", "persona": "Maria, 70 anni.", "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria. Hai male al ginocchio. Vuoi solo il Voltaren. Accetti il collagene SOLO se spiegano che la crema spegne il dolore oggi, ma il collagene ripara per domani.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai dimenticato il bancomat a casa, hai solo 15 euro in contanti. Chiedi se puoi prendere solo una cosa o se fanno credito.",
            "IMPREVISTO: Sei allergica ai FANS (Aspirina, Voltaren). Il farmacista deve cambiare protocollo (es. Arnica).",
            "IMPREVISTO: Tua figlia ti ha detto che il collagene fa ingrassare. Devi essere rassicurata."
        ]
    },
    "Cervicale e Stress": {
        "voice": "it-IT-DiegoNeural", "persona": "Marco, 45 anni.", "obiettivo": "Vendere: Cerotti + Magnesio.",
        "sys_prompt": "Sei Marco. Collo bloccato. Rifiuti magnesio. Accetti SOLO se spiegano che scioglie la contrattura muscolare.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai la pelle molto sensibile, i cerotti ti fanno allergia. Vedi se ti propone una crema.",
            "IMPREVISTO: Sei diabetico. Chiedi se il Magnesio contiene zucchero.",
            "IMPREVISTO: Hai frettissima, il taxi ti aspetta. Se il farmacista è lento, te ne vai."
        ]
    },
    "Mal di Testa (Donna)": {
        "voice": "it-IT-ElsaNeural", "persona": "Chiara, 30 anni.", "obiettivo": "Vendere: Ibuprofene + Coadiuvante.",
        "sys_prompt": "Sei Chiara. Cerchio alla testa. Vuoi il solito farmaco. Accetti integratore solo per stanchezza mentale.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sei incinta (o sospetti di esserlo). Il farmacista non può darti FANS, deve darti Paracetamolo.",
            "IMPREVISTO: Dì che la caffeina ti fa venire la tachicardia."
        ]
    },
    "Trauma Sportivo": {
        "voice": "it-IT-DiegoNeural", "persona": "Luca, 22 anni.", "obiettivo": "Vendere: Ghiaccio + Arnica.",
        "sys_prompt": "Sei Luca. Botta al ginocchio. Vuoi ghiaccio. Accetti Arnica solo se dimezza tempi recupero.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Dì che hai una partita domani mattina e devi giocare per forza. Chiedi un miracolo.",
            "IMPREVISTO: Dì che l'Arnica puzza e non vuoi usarla."
        ]
    },
    # --- 2. GASTRO ---
    "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural", "persona": "Giuseppe, 55 anni.", "obiettivo": "Vendere: Antiacido + Probiotici.",
        "sys_prompt": "Sei Giuseppe. Bruciore. Compri probiotici SOLO se spiegano che riparano la mucosa.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Soffri di pressione alta. Chiedi se l'antiacido ha sodio (sale).",
            "IMPREVISTO: Dì che i fermenti lattici ti gonfiano la pancia."
        ]
    },
    "Gonfiore Addominale": {
        "voice": "it-IT-ElsaNeural", "persona": "Simona, 35 anni.", "obiettivo": "Vendere: Carbone + Enzimi.",
        "sys_prompt": "Sei Simona. Gonfia. Rifiuti enzimi. Accetti SOLO se spiegano differenza col carbone.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Dì che devi andare a una cena di gala stasera e vuoi un effetto immediato, non una cura lunga.",
            "IMPREVISTO: Dì che prendi già carbone vegetale da un mese e non fa nulla."
        ]
    },
    "Terapia Antibiotica": {
        "voice": "it-IT-ElsaNeural", "persona": "Laura, 40 anni.", "obiettivo": "Vendere: Antibiotico + Fermenti.",
        "sys_prompt": "Sei Laura. Ricetta antibiotico. Rifiuti fermenti. Accetti SOLO se spiegano rischio diarrea.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Il bambino vomita le fialette. Serve un'altra forma farmaceutica (gocce/caramelle).",
            "IMPREVISTO: Chiedi se l'antibiotico va preso a stomaco pieno o vuoto (test competenza)."
        ]
    },
    "Stitichezza Occasionale": {
        "voice": "it-IT-DiegoNeural", "persona": "Paolo, 60 anni.", "obiettivo": "Vendere: Microclismi + Fibre.",
        "sys_prompt": "Sei Paolo. Bloccato. Vuoi purga. Accetti fibre solo per educare intestino.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Dì che hai le emorroidi infiammate, quindi hai paura a usare i microclismi.",
            "IMPREVISTO: Dì che bevi pochissima acqua e non hai intenzione di bere di più."
        ]
    },
    # --- 3. RESPIRATORIO ---
    "Tosse Secca (Fumatore)": {
        "voice": "it-IT-DiegoNeural", "persona": "Roberto, 50 anni.", "obiettivo": "Vendere: Sciroppo + Spray.",
        "sys_prompt": "Sei Roberto. Tosse fumo. Rifiuti spray. Accetti solo se protegge dal catrame.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sei diabetico, non puoi prendere sciroppi con zucchero.",
            "IMPREVISTO: Dì che tua moglie ti stressa per smettere di fumare, sei nervoso."
        ]
    },
    "Raffreddore": {
        "voice": "it-IT-ElsaNeural", "persona": "Anna, 28 anni.", "obiettivo": "Vendere: Decongestionante + Igiene Nasale.",
        "sys_prompt": "Sei Anna. Naso chiuso. Rifiuti lavaggi. Accetti solo se puliscono virus.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sei dipendente dallo spray nasale (Rinite medicamentosa), lo usi da 3 mesi. Il farmacista dovrebbe sgridarti."
        ]
    },
    "Mal di Gola": {
        "voice": "it-IT-DiegoNeural", "persona": "Andrea, 30 anni.", "obiettivo": "Vendere: Spray + Erisimo.",
        "sys_prompt": "Sei Andrea. Voce rauca. Accetti Erisimo solo per tono vocale.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sei un cantante lirico, non puoi usare prodotti con mentolo o alcol che seccano."
        ]
    },
    "Influenza": {
        "voice": "it-IT-ElsaNeural", "persona": "Giovanna, 75 anni.", "obiettivo": "Vendere: Tachipirina + Vit C.",
        "sys_prompt": "Sei Giovanna. Paura influenza. Accetti prevenzione solo per difese basse.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai difficoltà a deglutire le pastiglie grosse. Ti servono bustine.",
            "IMPREVISTO: Prendi il Coumadin (anticoagulante), chiedi se la Vitamina C interferisce."
        ]
    },
    # --- 4. BENESSERE ---
    "Insonnia": {
        "voice": "it-IT-ElsaNeural", "persona": "Giulia, 42 anni.", "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia. Dormi male. Scettica sul naturale.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Ti svegli sempre alle 3 di notte precise (risveglio precoce), la Melatonina semplice non basta (serve Retard)."
        ]
    },
    "Stanchezza Fisica": {
        "voice": "it-IT-DiegoNeural", "persona": "Luigi, 50 anni.", "obiettivo": "Vendere: Sali + Multivitaminico.",
        "sys_prompt": "Sei Luigi. Fiacco. Vuoi Polase. Accetti multi solo se copre tutto il giorno.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Soffri di calcoli renali, hai paura che gli integratori peggiorino la situazione."
        ]
    },
    "Anti-Age Viso": {
        "voice": "it-IT-ElsaNeural", "persona": "Elena, 55 anni.", "obiettivo": "Vendere: Crema + Siero.",
        "sys_prompt": "Sei Elena. Vuoi crema. Rifiuti siero. Accetti solo se veicola.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai la pelle mista che si lucida nella zona T. Non vuoi creme unte."
        ]
    },
    "Caduta Capelli": {
        "voice": "it-IT-ElsaNeural", "persona": "Francesca, 35 anni.", "obiettivo": "Vendere: Fiale + Integratore.",
        "sys_prompt": "Sei Francesca. Perdi capelli. Accetti integratore solo per materiale costruzione.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Stai allattando. Chiedi se puoi prendere questi prodotti."
        ]
    },
    # --- 5. SPECIALI ---
    "Cistite": {
        "voice": "it-IT-ElsaNeural", "persona": "Sara, 25 anni.", "obiettivo": "Vendere: Monuril + Fermenti.",
        "sys_prompt": "Sei Sara. Bruciore. Accetti fermenti solo per evitare recidive.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: È la quinta volta che ti viene quest'anno. Sei disperata."
        ]
    },
    "Occhi Secchi": {
        "voice": "it-IT-DiegoNeural", "persona": "Davide, 20 anni.", "obiettivo": "Vendere: Collirio + Integratore.",
        "sys_prompt": "Sei Davide. Occhi rossi PC. Accetti integratore solo per luce blu.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Porti le lenti a contatto. Ti serve un collirio compatibile."
        ]
    },
    "Gambe Pesanti": {
        "voice": "it-IT-ElsaNeural", "persona": "Rosa, 65 anni.", "obiettivo": "Vendere: Gel + Compresse.",
        "sys_prompt": "Sei Rosa. Caviglie gonfie. Accetti compresse solo per rinforzo vene.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Prendi farmaci per la tiroide. Chiedi se interferiscono."
        ]
    },
    "Colesterolo": {
        "voice": "it-IT-DiegoNeural", "persona": "Mario, 58 anni.", "obiettivo": "Vendere: Riso Rosso + Q10.",
        "sys_prompt": "Sei Mario. Colesterolo alto. Accetti Q10 solo per energia.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai dolori muscolari frequenti. Hai paura che il riso rosso li peggiori."
        ]
    }
}

# --- 5. FUNZIONI UTILI ---
async def text_to_speech(text, voice_id):
    try:
        communicate = edge_tts.Communicate(text, voice_id); await communicate.save("temp_audio.mp3"); return True
    except: return False

def autoplay_audio(file_path):
    with open(file_path, "rb") as f:
        data = f.read(); b64 = base64.b64encode(data).decode()
        md = f"""<audio controls autoplay style="width: 100%; margin-top: 5px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
        st.markdown(md, unsafe_allow_html=True)

def plot_radar(values):
    categories = ['Empatia', 'Tecnica', 'Chiusura', 'Ascolto', 'Gestione Imprevisto']
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='Tu'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, margin=dict(t=20, b=20, l=40, r=40))
    return fig

# --- 6. ADMIN DASHBOARD ---
def render_admin_dashboard():
    st.title("📊 PharmaBoss Dashboard")
    if not os.path.exists(KPI_FILE): st.warning("No dati."); return
    df = pd.read_csv(KPI_FILE)
    c1, c2, c3 = st.columns(3)
    c1.metric("Revenue Totale", f"€ {df['Revenue'].sum()}"); c2.metric("Voto Medio", f"{int(df['Score'].mean())}/100"); c3.metric("Simulazioni", len(df))
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🏆 Leaderboard")
        st.dataframe(df.groupby('User').agg({'Score':'mean','Revenue':'sum','Scenario':'count'}).reset_index().sort_values('Revenue', ascending=False), use_container_width=True, hide_index=True)
    with c2:
        st.subheader("📉 Analisi Casi")
        weak = df.groupby('Scenario')['Score'].mean().sort_values()
        st.plotly_chart(px.bar(weak, x='Score', y=weak.index, orientation='h', color='Score'), use_container_width=True)
    st.divider()
    st.subheader("🔎 Analisi Singola")
    sel = st.selectbox("Farmacista:", df['User'].unique())
    # Mostriamo anche il Twist nel report
    st.table(df[df['User']==sel][['Scenario', 'Score']].tail(5))

# --- 7. SIDEBAR ---
if "logged_in" not in st.session_state: st.session_state.logged_in=False; st.session_state.user_info={}
with st.sidebar:
    st.title("PharmaFlow 🎲")
    if st.session_state.logged_in:
        u = st.session_state.user_info; st.write(f"**{u['avatar']} {u['name']}**")
        if st.button("Logout"): st.session_state.logged_in=False; st.rerun()
    st.divider()
    admin_mode = st.checkbox("🔐 Admin Area")
    if admin_mode and st.text_input("Pwd", type="password")!=ADMIN_PASS: admin_mode=False

# --- 8. APP LOGIC ---
if admin_mode: render_admin_dashboard(); st.stop()

if not st.session_state.logged_in:
    t1, t2 = st.tabs(["Accedi", "Registrati"])
    with t1:
        with st.form("l"):
            u=st.text_input("User"); p=st.text_input("Pass", type="password")
            if st.form_submit_button("Entra"):
                d = login_user(u,p); 
                if d: st.session_state.logged_in=True; st.session_state.user_info=d; st.rerun()
                else: st.error("Errore")
    with t2:
        with st.form("r"):
            nu=st.text_input("User"); np=st.text_input("Pass", type="password"); fn=st.text_input("Nome"); ge=st.selectbox("Sesso",["Uomo","Donna"])
            if st.form_submit_button("Crea"):
                if save_user(nu,np,fn,ge): st.success("Ok!"); else: st.error("Esiste già")
    st.stop()

# --- TRAINING INTERFACE ---
sel_scenario = st.sidebar.selectbox("Scenario:", list(SCENARIOS.keys()))
hard = st.sidebar.toggle("🔥 Hard Mode")

# --- LOGICA ROGUE MODE (Imprevedibilità) ---
# Se cambiamo scenario o clicchiamo reset, peschiamo un nuovo imprevisto
if "current_scenario" not in st.session_state: st.session_state.current_scenario = ""
if "current_twist" not in st.session_state: st.session_state.current_twist = ""

trigger_reset = st.sidebar.button("🎲 Nuova Simulazione")

if trigger_reset or st.session_state.current_scenario != sel_scenario:
    st.session_state.messages = []
    st.session_state.current_scenario = sel_scenario
    # Pesca un imprevisto casuale dalla lista dello scenario
    possible_twists = SCENARIOS[sel_scenario].get('twists', ["Nessun imprevisto."])
    st.session_state.current_twist = random.choice(possible_twists)
    st.rerun()

curr = SCENARIOS[sel_scenario]
st.header(f"Simulazione: {sel_scenario}")
st.markdown(f"**Obiettivo:** {curr['obiettivo']}")

# Visualizzazione (Opzionale, utile per capire se funziona)
# st.caption(f"Debug Twist: {st.session_state.current_twist}")

if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages: 
    with st.chat_message(m["role"]): st.write(m["content"])

# Tutor
if st.button("💡 Suggerimento"):
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    h = get_ai_response([{"role":"system","content":f"Tutor per: {curr['obiettivo']}. Suggerisci frase breve."},{"role":"user","content":hist}])
    st.info(f"Tip: {h}")

# --- INPUT AREA ---
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

# --- ESECUZIONE CHAT ---
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"): st.write(final_input)
    
    with st.spinner("..."):
        # INIEZIONE DEL TWIST NEL PROMPT DI SISTEMA
        twist_instruction = f" ISTRUZIONE SPECIALE/IMPREVISTO PER QUESTA SESSIONE: {st.session_state.current_twist}. Devi agire tenendo conto di questo imprevisto."
        sys = curr['sys_prompt'] + (" Sii scontroso." if hard else "") + twist_instruction
        
        ai_msg = get_ai_response([{"role":"system","content":sys}] + st.session_state.messages)
        asyncio.run(text_to_speech(ai_msg, curr['voice']))
    
    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
    with st.chat_message("assistant"): st.write(ai_msg); autoplay_audio("temp_audio.mp3")

# Evaluation
if len(st.session_state.messages)>2 and st.button("🏁 Valuta", type="primary", use_container_width=True):
    with st.spinner("Analisi..."):
        hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        # Informiamo il Giudice dell'imprevisto, così può valutare se è stato gestito
        prompt = f"Analisi {sel_scenario}. IMPREVISTO GESTITO: {st.session_state.current_twist}. JSON: {{'score_empatia':1-10, 'score_tecnica':1-10, 'score_chiusura':1-10, 'score_ascolto':1-10, 'score_obiezioni':1-10, 'totale':0-100, 'revenue':euro, 'feedback_main':'txt', 'mistake':'txt', 'correction':'txt'}}\nCHAT:\n{hist}"
        res = get_ai_response([{"role":"user","content":prompt}], json_mode=True)
        try:
            d = json.loads(res)
            st.balloons()
            t1, t2 = st.tabs(["Performance", "Dettagli"])
            with t1: 
                c1,c2=st.columns(2)
                # Radar aggiornato con 'Gestione Imprevisto'
                c1.plotly_chart(plot_radar([d['score_empatia'],d['score_tecnica'],d['score_chiusura'],d['score_ascolto'],d['score_obiezioni']]))
                c2.metric("Voto", f"{d['totale']}/100"); c2.metric("Fatturato", f"€ {d['revenue']}")
                if st.session_state.current_twist != "Nessun imprevisto.":
                    st.info(f"Twist Affrontato: {st.session_state.current_twist}")
            with t2: st.error(d['mistake']); st.success(d['correction'])
            
            row = {"Date":datetime.now().strftime("%Y-%m-%d %H:%M"), "User": st.session_state.user_info['name'], "Scenario": sel_scenario, "Score": d['totale'], "Revenue": d['revenue']}
            try: pd.read_csv(KPI_FILE)._append(row, ignore_index=True).to_csv(KPI_FILE, index=False)
            except: pd.DataFrame([row]).to_csv(KPI_FILE, index=False)
        except: st.error("Errore report")