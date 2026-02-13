import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts

# --- 1. CONFIGURAZIONE E SICUREZZA ---

try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    # Utilizziamo l'endpoint più stabile per Gemini 1.5 Pro
    model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
except Exception as e:
    st.error("Errore: GOOGLE_API_KEY non configurata correttamente nei Secrets.")
    st.stop()

# --- 2. FUNZIONI DI SISTEMA (Database e Audio) ---

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

    st.set_page_config(page_title="PharmaFlow Pro - Login", page_icon="💊")
    st.title("🛡️ Accesso PharmaFlow AI Pro")
    st.markdown("Piattaforma di Alta Formazione per Farmacisti.")
    
    nome_utente = st.text_input("Nome e Cognome del Professionista:")
    password = st.text_input("Password Aziendale:", type="password")
    
    if st.button("Accedi"):
        if password == st.secrets["APP_PASSWORD"] and nome_utente.strip() != "":
            st.session_state.password_correct = True
            st.session_state.user_name = nome_utente.strip()
            st.rerun()
        else:
            st.error("Credenziali errate o nome mancante.")
    return False

if not check_password():
    st.stop()

# --- 4. DATASET SCENARI ---

SCENARIOS = {
    "Dolore Ginocchio 🦵": {
        "persona": "Maria, 65 anni, diffidente.",
        "sintomo": "Dolore al ginocchio che non passa.",
        "obiettivo_vendita": "Protocollo: Crema Antinfiammatoria + Collagene Idrolizzato.",
        "prompt_cliente": "Sei Maria. Hai male al ginocchio. Sei tirchia. Accetti il collagene solo se ti spiegano chiaramente che non è una semplice vitamina ma rigenera la cartilagine."
    },
    "Tosse Secca 😷": {
        "persona": "Luca, 30 anni, fumatore, ha fretta.",
        "sintomo": "Tosse stizzosa che non mi fa dormire.",
        "obiettivo_vendita": "Protocollo: Sciroppo Sedativo + Spray Gola Protettivo.",
        "prompt_cliente": "Sei Luca. Hai fretta. Accetti lo spray solo se ti dicono che crea un film protettivo per calmare l'irritazione da fumo."
    },
    "Insonnia 🌙": {
        "persona": "Giulia, 40 anni, manager stressata.",
        "sintomo": "Risvegli notturni alle 3.",
        "obiettivo_vendita": "Protocollo: Melatonina Retard + Magnesio.",
        "prompt_cliente": "Sei Giulia. Ansiosa. Accetti il magnesio solo se ti spiegano che rilassa i muscoli e calma lo stress mentale."
    }
}

# --- 5. INTERFACCIA E CHAT ---

st.sidebar.title(f"👤 Dr. {st.session_state.user_name}")
scenario_name = st.sidebar.selectbox("Seleziona Scenario Clinico:", list(SCENARIOS.keys()))
current_scenario = SCENARIOS[scenario_name]

st.sidebar.info(f"🎯 **Obiettivo:** {current_scenario['obiettivo_vendita']}")

if st.sidebar.button("🔄 Nuova Sessione"):
    st.session_state.messages = []
    st.rerun()

st.title(f"Simulazione: {scenario_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Visualizzazione cronologia
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_input = st.chat_input("Formula la tua proposta al paziente...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Il cliente riflette..."):
        # Costruzione history per Gemini (ruoli 'user' e 'model')
        formatted_history = []
        for m in st.session_state.messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            formatted_history.append({"role": role, "parts": [m["content"]]})
        
        chat = model.start_chat(history=formatted_history)
        
        try:
            # Invio messaggio con istruzioni di sistema contestuali
            response = chat.send_message(
                f"SISTEMA: {current_scenario['prompt_cliente']} Rispondi in italiano, max 2 frasi.\nUTENTE: {user_input}"
            )
            ai_response = response.text
            
            # Audio e Autoplay
            asyncio.run(generate_audio(ai_response))
            with open("response.mp3", "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)
            
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()

        except Exception as e:
            st.error(f"Errore API Gemini: {e}")

# --- 6. IL GIUDICE (ANALISI GEMINI 3 PRO) ---

if len(st.session_state.messages) > 1:
    st.divider()
    if st.button("🏁 TERMINA E VALUTA PERFORMANCE"):
        with st.spinner("Il Consulente AI sta analizzando la sessione..."):
            chat_history = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
            
            judge_prompt = f"""
            Sei un Senior Consultant per farmacie d'elite. 
            Valuta la vendita per lo scenario: {current_scenario['sintomo']}.
            Obiettivo richiesto: {current_scenario['obiettivo_vendita']}.
            
            Restituisci ESCLUSIVAMENTE un JSON:
            {{
              "score": (numero 0-100),
              "margine_euro": (numero stimato 5-40),
              "feedback": "analisi critica breve",
              "consiglio": "frase d'oro da dire"
            }}
            """
            
            try:
                res_ai = model.generate_content(judge_prompt + "\n\nTRASCRIZIONE:\n" + chat_history)
                
                # Pulizia JSON
                json_str = res_ai.text.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0]
                
                res = json.loads(json_str)
                
                st.header("🏆 Report di Valutazione")
                c1, c2 = st.columns(2)
                c1.metric("Punteggio", f"{res['score']}/100")
                c2.metric("Extra Margine", f"€ {res['margine_euro']}")
                
                st.info(f"**Feedback Tecnico:** {res['feedback']}")
                st.success(f"**Consiglio del Coach:** {res['consiglio']}")
                
                registra_simulazione(st.session_state.user_name, scenario_name, res['score'], res['margine_euro'])
                
            except Exception as e:
                st.error("Errore nell'analisi. Gemini ha risposto in modo non strutturato.")
                st.write(res_ai.text)

# --- 7. DASHBOARD ANALYTICS ---

st.sidebar.divider()
if st.sidebar.checkbox("📊 Dashboard Titolare"):
    st.title("📈 Business Intelligence")
    try:
        df_dash = pd.read_csv("storico_performance.csv")
        
        col1, col2 = st.columns(2)
        col1.metric("Margine Totale Stimato", f"€ {df_dash['Margine_Potenziale'].sum()}")
        col2.metric("Punteggio Medio Team", f"{int(df_dash['Punteggio'].mean())}/100")
        
        st.subheader("Storico Sessioni")
        st.dataframe(df_dash.sort_values(by="Data", ascending=False), use_container_width=True)
        
        st.subheader("Andamento Performance")
        st.line_chart(df_dash.set_index("Data")["Punteggio"])
        
    except:
        st.info("Nessun dato registrato. Completa la prima simulazione.")