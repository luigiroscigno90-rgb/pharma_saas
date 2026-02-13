import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts

# --- 1. CONFIGURAZIONE MOTORE ---
st.set_page_config(page_title="PharmaFlow AI Pro", page_icon="💊", layout="wide")

# Forza l'uso dell'endpoint stabile per evitare l'errore v1beta
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # Nome modello esplicito con prefisso per massima compatibilità con la v0.8.6
    model = genai.GenerativeModel(model_name='models/gemini-1.5-flash') 
except Exception as e:
    st.error(f"⚠️ Errore configurazione: {e}")
    st.stop()

# --- 2. FUNZIONI DI SISTEMA ---

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

# --- 3. LOGIN SYSTEM ---

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True

    st.title("🛡️ PharmaFlow AI Pro - Accesso Riservato")
    with st.form("login_form"):
        nome_utente = st.text_input("Identificativo Professionista:")
        password = st.text_input("Password di Accesso:", type="password")
        submit = st.form_submit_button("Sblocca Sistema")
        if submit:
            if password == st.secrets["APP_PASSWORD"] and nome_utente.strip() != "":
                st.session_state.password_correct = True
                st.session_state.user_name = nome_utente.strip()
                st.rerun()
            else:
                st.error("Credenziali non valide.")
    return False

if not check_password():
    st.stop()

# --- 4. DATASET SCENARI ---

SCENARIOS = {
    "Dolore Ginocchio 🦵": {
        "persona": "Maria, 65 anni, diffidente.",
        "obiettivo_vendita": "Protocollo: Crema Antinfiammatoria + Ciclo Collagene.",
        "prompt_cliente": "Sei Maria. Hai male al ginocchio. Sei tirchia. Accetti il collagene solo se ti spiegano che la crema cura il sintomo, ma il collagene rigenera la cartilagine."
    },
    "Tosse Secca 😷": {
        "persona": "Luca, 30 anni, fumatore.",
        "obiettivo_vendita": "Protocollo: Sciroppo Sedativo + Spray Gola Protettivo.",
        "prompt_cliente": "Sei Luca. Hai fretta. Accetti lo spray solo se ti dicono che protegge la gola irritata dal fumo."
    }
}

# --- 5. INTERFACCIA ---

st.sidebar.title(f"👨‍⚕️ Dr. {st.session_state.user_name}")
scenario_name = st.sidebar.selectbox("Caso Clinico:", list(SCENARIOS.keys()))
current_scenario = SCENARIOS[scenario_name]

if st.sidebar.button("🔄 Reset Simulazione"):
    st.session_state.messages = []
    st.rerun()

st.title(f"Simulazione: {scenario_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# --- 6. CHAT LOGIC (BYPASS MODALITÀ CHAT PER EVITARE 404) ---

user_input = st.chat_input("Digita il tuo consiglio professionale...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Il cliente risponde..."):
        try:
            # Costruiamo il contesto testuale completo
            full_history = ""
            for m in st.session_state.messages:
                full_history += f"{m['role']}: {m['content']}\n"
            
            prompt_engine = f"""
            {current_scenario['prompt_cliente']}
            Rispondi in modo breve (max 2 frasi).
            STORIA CONVERSAZIONE:
            {full_history}
            """
            
            # Chiamata diretta generate_content (più stabile)
            response = model.generate_content(prompt_engine)
            ai_response = response.text

            asyncio.run(generate_audio(ai_response))
            with open("response.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()

        except Exception as e:
            st.error(f"Dettaglio Errore: {e}")

# --- 7. IL GIUDICE ---

if len(st.session_state.messages) > 1:
    st.divider()
    if st.button("🏁 ANALIZZA PERFORMANCE"):
        with st.spinner("Valutazione in corso..."):
            chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
            
            judge_prompt = f"""
            Analizza questa vendita farmaceutica. Scenario: {scenario_name}.
            Restituisci SOLO un JSON:
            {{ "score": 0-100, "margine_euro": 5-30, "feedback": "...", "consiglio": "..." }}
            \n\nTRASCRIZIONE:\n{chat_text}
            """
            
            try:
                res_ai = model.generate_content(judge_prompt)
                json_clean = res_ai.text.replace('```json', '').replace('```', '').strip()
                res = json.loads(json_clean)
                
                st.header("📊 Verdetto Strategico")
                st.metric("Punteggio", f