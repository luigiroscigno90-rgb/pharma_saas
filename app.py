import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts

# --- 1. CONFIGURAZIONE DINAMICA ---
st.set_page_config(page_title="PharmaFlow AI", page_icon="💊", layout="wide")

# Funzione che TROVA il modello invece di indovinarlo
def get_best_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # Chiediamo a Google: "Cosa posso usare?"
        modelli_disponibili = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelli_disponibili.append(m.name)
        
        # Cerchiamo il migliore in ordine di priorità
        # 1. Cerchiamo Flash (veloce ed economico)
        for m in modelli_disponibili:
            if 'flash' in m.lower():
                return genai.GenerativeModel(m)
        
        # 2. Se non c'è Flash, cerchiamo Pro
        for m in modelli_disponibili:
            if 'pro' in m.lower() and 'vision' not in m.lower():
                return genai.GenerativeModel(m)
                
        # 3. Se va male, prendiamo il primo della lista (spesso 'gemini-pro')
        if modelli_disponibili:
            return genai.GenerativeModel(modelli_disponibili[0])
            
    except Exception as e:
        st.error(f"Errore connessione Google: {e}")
        st.stop()
    
    st.error("Nessun modello compatibile trovato nella tua Chiave API.")
    st.stop()

# Inizializza il modello trovato
model = get_best_model()

# --- 2. STORAGE ---
def registra_simulazione(nome, scenario, punteggio, margine):
    file_nome = "storico_performance.csv"
    nuova_riga = {
        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "Farmacista": nome,
        "Scenario": scenario,
        "Punteggio": punteggio,
        "Margine": margine
    }
    try:
        df = pd.read_csv(file_nome)
        df = pd.concat([df, pd.DataFrame([nuova_riga])], ignore_index=True)
    except FileNotFoundError:
        df = pd.DataFrame([nuova_riga])
    df.to_csv(file_nome, index=False)

async def generate_audio(text):
    communicate = edge_tts.Communicate(text, "it-IT-ElsaNeural")
    await communicate.save("response.mp3")

# --- 3. LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct: return True

    st.title("🛡️ PharmaFlow AI")
    pwd = st.text_input("Password:", type="password")
    user = st.text_input("Nome:")
    if st.button("Entra"):
        if pwd == st.secrets["APP_PASSWORD"] and user:
            st.session_state.password_correct = True
            st.session_state.user_name = user
            st.rerun()
    return False

if not check_password(): st.stop()

# --- 4. SCENARI ---
SCENARIOS = {
    "Ginocchio 🦵": {
        "prompt": "Sei Maria, 65 anni. Hai male al ginocchio. Sei diffidente. Accetti il collagene solo se ti spiegano che rigenera la cartilagine.",
        "kpi": "Vendere Crema + Collagene"
    },
    "Tosse 😷": {
        "prompt": "Sei Luca, 30 anni, fumatore. Hai fretta. Accetti lo spray solo se ti dicono che protegge la gola.",
        "kpi": "Vendere Sciroppo + Spray"
    }
}

# --- 5. CHAT ---
st.sidebar.title(f"Dr. {st.session_state.user_name}")
scelta = st.sidebar.selectbox("Scenario:", list(SCENARIOS.keys()))
dati_scenario = SCENARIOS[scelta]

if st.sidebar.button("Reset"):
    st.session_state.messages = []
    st.rerun()

st.title(scelta)

if "messages" not in st.session_state: st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.write(m["content"])

user_input = st.chat_input("Scrivi qui...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)

    with st.spinner("..."):
        try:
            # Costruiamo il prompt completo (metodo infallibile)
            storia = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            full_prompt = f"{dati_scenario['prompt']}\nRispondi brevemente.\nSTORIA:\n{storia}"
            
            # Chiamata diretta
            response = model.generate_content(full_prompt)
            ai_text = response.text

            # Audio
            asyncio.run(generate_audio(ai_text))
            with open("response.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

            st.session_state.messages.append({"role": "assistant", "content": ai_text})
            st.rerun()
        except Exception as e:
            st.error(f"Errore AI: {e}")

# --- 6. ANALISI ---
if st.button("🏁 VALUTA"):
    with st.spinner("Analisi..."):
        storia = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        prompt = f"Analizza vendita: {dati_scenario['kpi']}.\nJSON: {{'score': 0-100, 'margine': 0-30, 'feedback': '...'}}\n{storia}"
        try:
            res = model.generate_content(prompt)
            clean_json = res.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_json)
            st.metric("Voto", f"{data['score']}/100")
            st.metric("Margine", f"€ {data['margine']}")
            st.info(data['feedback'])
            registra_simulazione(st.session_state.user_name, scelta, data['score'], data['margine'])
        except:
            st.error("Errore analisi")

# --- 7. DASHBOARD ---
if st.sidebar.checkbox("Dashboard"):
    try:
        df = pd.read_csv("storico_performance.csv")
        st.dataframe(df)
    except: st.write("No dati")