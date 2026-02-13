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
import hashlib # Per criptare le password

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI Team", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f0f2f6;}
    div[data-testid="stSidebar"] {background-color: #1a252f; color: white;}
    .stChatInput {border-radius: 20px;}
    .stButton button {border-radius: 8px; font-weight: 600;}
    /* Tab System pulito */
    .stTabs [data-baseweb="tab-list"] {gap: 10px;}
    .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; background-color: white; border-radius: 5px;}
    .stTabs [aria-selected="true"] {background-color: #e8f0fe; color: #1a73e8;}
    </style>
""", unsafe_allow_html=True)

# --- 2. SISTEMA DI AUTENTICAZIONE (AUTH) ---
DB_FILE = "users_db.json"

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return hashed_text
    return False

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_user(username, password, name, gender):
    users = load_users()
    if username in users:
        return False # Utente esiste già
    users[username] = {
        "password": make_hashes(password),
        "name": name,
        "gender": gender, # 'M' o 'F'
        "avatar": "👨‍⚕️" if gender == "Uomo" else "👩‍⚕️"
    }
    with open(DB_FILE, "w") as f:
        json.dump(users, f)
    return True

def login_user(username, password):
    users = load_users()
    if username in users:
        if check_hashes(password, users[username]['password']):
            return users[username]
    return None

# --- 3. MOTORE AI (GROQ) ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("⚠️ Manca la GROQ_API_KEY nei secrets!")
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

# --- 4. DATABASE SCENARI ---
SCENARIOS = {
    "Dolore Articolare": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Maria, 68 anni.",
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria, 68 anni. Diffidente. Hai male al ginocchio. Vuoi solo la crema. Accetti il collagene SOLO se il farmacista ti spiega che la crema toglie il dolore oggi, ma il collagene ripara la cartilagine per il futuro. Rispondi in max 20 parole."
    },
    "Tosse Fumatore": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Luca, 35 anni.",
        "obiettivo": "Vendere: Sciroppo + Spray Gola.",
        "sys_prompt": "Sei Luca, 35 anni, fumatore. Hai fretta. Accetti lo spray SOLO se ti dicono che crea una barriera protettiva contro il fumo. Sii sbrigativo. Rispondi in max 15 parole."
    },
    "Insonnia Stress": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Giulia, 42 anni.",
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia, manager stressata. Vuoi farmaci forti. Accetti integratori SOLO se ti spiegano l'azione rilassante sul sistema nervoso. Sii scettica."
    },
     "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Marco, 50 anni.",
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

# --- 6. GESTIONE STATO E LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

# --- SCHERMATA LOGIN / REGISTRAZIONE ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🏥 PharmaFlow Team Access")
        st.write("Accedi al portale di formazione continua.")
        
        tab_login, tab_register = st.tabs(["🔑 Accedi", "📝 Registrati"])
        
        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit_login = st.form_submit_button("Entra")
                
                if submit_login:
                    user_data = login_user(username, password)
                    if user_data:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_data
                        st.success("Login effettuato!")
                        st.rerun()
                    else:
                        st.error("Username o password errati.")
        
        with tab_register:
            with st.form("reg_form"):
                new_user = st.text_input("Scegli un Username")
                new_pass = st.text_input("Scegli una Password", type="password")
                full_name = st.text_input("Nome e Cognome (es. Dr. Mario Rossi)")
                gender = st.selectbox("Sesso (per Avatar)", ["Uomo", "Donna"])
                submit_reg = st.form_submit_button("Crea Account")
                
                if submit_reg:
                    if new_user and new_pass and full_name:
                        if save_user(new_user, new_pass, full_name, gender):
                            st.success("Account creato! Ora puoi accedere.")
                        else:
                            st.error("Username già in uso.")
                    else:
                        st.warning("Compila tutti i campi.")
    st.stop() # Ferma l'esecuzione se non loggato

# --- 7. SIDEBAR (LOGGATO) ---
user = st.session_state.user_info

with st.sidebar:
    # Avatar Dinamico e Nome
    st.title(f"{user['avatar']} PharmaFlow")
    st.write(f"**{user['name']}**")
    
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = {}
        st.rerun()
        
    st.divider()
    
    selected_scenario = st.selectbox("Seleziona Scenario:", list(SCENARIOS.keys()))
    hard_mode = st.toggle("🔥 Hard Mode", value=False)
    
    if st.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- 8. MAIN APP LOGIC ---
current_data = SCENARIOS[selected_scenario]
st.header(f"Simulazione: {selected_scenario}")
st.markdown(f"**Paziente:** {current_data['persona']} | **Obiettivo:** {current_data['obiettivo']}")

if "messages" not in st.session_state: st.session_state.messages = []

# Mostra Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.write(msg["content"])

# Tutor Hint
col_hint, col_space = st.columns([1, 4])
with col_hint:
    if st.button("💡 Suggerimento"):
        with st.spinner("Thinking..."):
            hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            hint_prompt = [{"role": "system", "content": f"Sei un tutor. Obiettivo: {current_data['obiettivo']}. Suggerisci una frase breve per il farmacista."}, {"role": "user", "content": hist}]
            hint = get_ai_response(hint_prompt)
            st.info(f"Prova a dire: {hint}")

# Input Utente
user_input = st.chat_input("Scrivi la tua risposta...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)
    
    with st.spinner("Il paziente risponde..."):
        sys_prompt = current_data['sys_prompt']
        if hard_mode: sys_prompt += " Sii scontroso e polemico sui prezzi."
        
        msgs = [{"role": "system", "content": sys_prompt}] + st.session_state.messages
        ai_reply = get_ai_response(msgs)
        asyncio.run(text_to_speech(ai_reply, current_data['voice']))

    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
    with st.chat_message("assistant"):
        st.write(ai_reply)
        autoplay_audio("temp_audio.mp3")

# Analisi Finale
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 TERMINA E VALUTA", type="primary", use_container_width=True):
        with st.spinner("Generazione Report per il Titolare..."):
            hist_txt = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            judge_prompt = f"""
            Analizza vendita. SCENARIO: {selected_scenario}. OBIETTIVO: {current_data['obiettivo']}.
            JSON ONLY: {{
                "score_empatia": (1-10), "score_tecnica": (1-10), "score_chiusura": (1-10),
                "score_ascolto": (1-10), "score_obiezioni": (1-10), "totale": (0-100),
                "revenue": (stima euro), "feedback_main": "breve", "mistake": "breve", "correction": "breve"
            }}
            CHAT: {hist_txt}
            """
            res_json = get_ai_response([{"role": "user", "content": judge_prompt}], json_mode=True)
            
            try:
                data = json.loads(res_json)
                st.balloons()
                
                tab1, tab2 = st.tabs(["📊 Performance", "📝 Dettagli"])
                with tab1:
                    c1, c2 = st.columns(2)
                    with c1:
                        vals = [data['score_empatia'], data['score_tecnica'], data['score_chiusura'], data['score_ascolto'], data['score_obiezioni']]
                        st.plotly_chart(plot_radar(vals), use_container_width=True)
                    with c2:
                        st.metric("Voto Finale", f"{data['totale']}/100")
                        st.metric("Fatturato", f"€ {data['revenue']}")
                        st.info(data['feedback_main'])
                
                with tab2:
                    st.error(f"Errore: {data['mistake']}")
                    st.success(f"Correzione: {data['correction']}")
                
                # Salvataggio con Nome Utente REALE
                file = "kpi_db.csv"
                new_row = {"Date": datetime.now(), "User": user['name'], "Scenario": selected_scenario, "Score": data['totale'], "Revenue": data['revenue']}
                try: pd.read_csv(file)._append(new_row, ignore_index=True).to_csv(file, index=False)
                except: pd.DataFrame([new_row]).to_csv(file, index=False)

            except: st.error("Errore report.")