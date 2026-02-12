import streamlit as st
import os
from groq import Groq
import asyncio
import edge_tts
import pandas as pd
from datetime import datetime
import json
import base64

# --- 1. FUNZIONI DI SISTEMA (Database e Audio) ---

def registra_simulazione(nome, scenario, punteggio, margine):
    file_nome = "storico_performance.csv"
    nuova_riga = {
        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "Farmacista": nome,
        "Scenario": scenario,
        "Punteggio": punteggio,
        "Margine_Potenziale": margine
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

# --- 2. LOGIN SYSTEM ---

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    st.set_page_config(page_title="PharmaFlow AI - Login", page_icon="💊")
    st.title("🛡️ Accesso PharmaFlow AI")
    st.markdown("Inserisci le tue credenziali per iniziare l'allenamento.")
    
    nome_utente = st.text_input("Nome e Cognome del Farmacista:")
    password = st.text_input("Password di Accesso:", type="password")
    
    if st.button("Accedi al Sistema"):
        if password == st.secrets["APP_PASSWORD"] and nome_utente.strip() != "":
            st.session_state.password_correct = True
            st.session_state.user_name = nome_utente.strip()
            st.rerun()
        else:
            st.error("Credenziali errate o nome mancante.")
    return False

if not check_password():
    st.stop()

# --- 3. CONFIGURAZIONE AI ---

try:
    API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=API_KEY)
except Exception as e:
    st.error("Errore configurazione API Key. Controlla i Secrets.")
    st.stop()

# --- 4. SCENARI E INTERFACCIA ---

SCENARIOS = {
    "Dolore Ginocchio 🦵": {
        "persona": "Maria, 65 anni, diffidente.",
        "sintomo": "Dolore al ginocchio che non passa.",
        "obiettivo_vendita": "Protocollo: Crema Antinfiammatoria + Collagene Idrolizzato.",
        "prompt_cliente": "Sei Maria. Hai male al ginocchio. Sei tirchia. Accetti il collagene solo se ti spiegano che rigenera la cartilagine."
    },
    "Tosse Secca 😷": {
        "persona": "Luca, 30 anni, fumatore, ha fretta.",
        "sintomo": "Tosse stizzosa che non mi fa dormire.",
        "obiettivo_vendita": "Protocollo: Sciroppo Sedativo + Spray Gola Protettivo.",
        "prompt_cliente": "Sei Luca. Hai fretta. Accetti lo spray solo se ti dicono che protegge la gola irritata dal fumo."
    },
    "Insonnia 🌙": {
        "persona": "Giulia, 40 anni, manager stressata.",
        "sintomo": "Risvegli notturni alle 3.",
        "obiettivo_vendita": "Protocollo: Melatonina Retard + Magnesio.",
        "prompt_cliente": "Sei Giulia. Ansiosa. Accetti il magnesio solo se ti spiegano che rilassa i muscoli tesi dallo stress."
    }
}

st.sidebar.title(f"👤 {st.session_state.user_name}")
scenario_name = st.sidebar.selectbox("Scegli Scenario:", list(SCENARIOS.keys()))
current_scenario = SCENARIOS[scenario_name]

st.sidebar.info(f"🎯 **Obiettivo:** {current_scenario['obiettivo_vendita']}")

if st.sidebar.button("🔄 Nuova Sessione"):
    st.session_state.messages = []
    st.rerun()

# --- 5. CHAT ENGINE ---

st.title(f"Simulazione: {scenario_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_input = st.chat_input("Scrivi qui...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Il cliente risponde..."):
        sys_prompt = f"{current_scenario['prompt_cliente']} Rispondi brevemente (max 2 frasi)."
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages,
            temperature=0.7
        )
        ai_response = completion.choices[0].message.content
        
        # Audio Autoplay
        asyncio.run(generate_audio(ai_response))
        with open("response.mp3", "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

    st.session_state.messages.append({"role": "assistant", "content": ai_response})
    with st.chat_message("assistant"):
        st.write(ai_response)
        st.audio("response.mp3", format="audio/mp3")

# --- 6. IL GIUDICE E DASHBOARD ---

if len(st.session_state.messages) > 1:
    st.divider()
    if st.button("🏁 VALUTA LA MIA VENDITA"):
        with st.spinner("Analisi in corso..."):
            chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
            
            judge_prompt = f"""
            Sei un esperto di vendita farmaceutica. Valuta lo scenario: {current_scenario['sintomo']}.
            Obiettivo: {current_scenario['obiettivo_vendita']}.
            Restituisci JSON: {{"score": 0-100, "margine_euro": 5-30, "feedback": "...", "consiglio": "..."}}
            """
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": judge_prompt}, {"role": "user", "content": chat_text}],
                temperature=0.2
            )
            
            res = json.loads(completion.choices[0].message.content[completion.choices[0].message.content.find('{'):completion.choices[0].message.content.rfind('}')+1])
            
            st.success("Valutazione completata!")
            st.metric("Punteggio", f"{res['score']}/100", delta=f"€{res['margine_euro']} Margine")
            st.info(f"**Feedback:** {res['feedback']}")
            
            registra_simulazione(st.session_state.user_name, scenario_name, res['score'], res['margine_euro'])

# DASHBOARD LATERALE
st.sidebar.divider()
if st.sidebar.checkbox("📊 Dashboard Titolare"):
    st.title("Dashboard Analytics")
    try:
        df_dash = pd.read_csv("storico_performance.csv")
        st.metric("Margine Totale Stimato", f"€ {df_dash['Margine_Potenziale'].sum()}")
        st.subheader("Performance Team")
        st.dataframe(df_dash)
    except:
        st.info("Nessun dato registrato.")