import streamlit as st
import google.generativeai as genai
# Forza l'uso di v1 se disponibile
os.environ["GOOGLE_GENAI_USE_V1"] = "1"
import os
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts

# --- 1. CONFIGURAZIONE E SICUREZZA ---

# Nota: Assicurati di avere GOOGLE_API_KEY e APP_PASSWORD nei Secrets
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # Utilizziamo la versione flash-latest per massima stabilità
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("Errore di configurazione API. Verifica i Secrets.")
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

    st.set_page_config(page_title="PharmaFlow Pro", page_icon="💊")
    st.title("🛡️ Accesso PharmaFlow AI Pro")
    
    nome_utente = st.text_input("Nome Professionista:")
    password = st.text_input("Password:", type="password")
    
    if st.button("Entra"):
        if password == st.secrets["APP_PASSWORD"] and nome_utente.strip() != "":
            st.session_state.password_correct = True
            st.session_state.user_name = nome_utente.strip()
            st.rerun()
        else:
            st.error("Credenziali errate.")
    return False

if not check_password():
    st.stop()

# --- 4. DATASET SCENARI ---

SCENARIOS = {
    "Dolore Ginocchio 🦵": {
        "persona": "Maria, 65 anni, diffidente.",
        "obiettivo_vendita": "Protocollo: Crema Antinfiammatoria + Collagene Idrolizzato.",
        "prompt_cliente": "Sei Maria. Hai male al ginocchio. Sei tirchia. Accetti il collagene solo se ti spiegano che rigenera la cartilagine."
    },
    "Tosse Secca 😷": {
        "persona": "Luca, 30 anni, fumatore.",
        "obiettivo_vendita": "Protocollo: Sciroppo Sedativo + Spray Gola.",
        "prompt_cliente": "Sei Luca. Hai fretta. Accetti lo spray solo se ti dicono che protegge la gola dal fumo."
    },
    "Insonnia 🌙": {
        "persona": "Giulia, 40 anni, manager stressata.",
        "obiettivo_vendita": "Protocollo: Melatonina Retard + Magnesio.",
        "prompt_cliente": "Sei Giulia. Ansiosa. Accetti il magnesio solo se ti spiegano che rilassa i muscoli tesi."
    }
}

# --- 5. INTERFACCIA ---

st.sidebar.title(f"👤 Dr. {st.session_state.user_name}")
scenario_name = st.sidebar.selectbox("Caso del giorno:", list(SCENARIOS.keys()))
current_scenario = SCENARIOS[scenario_name]
st.sidebar.info(f"🎯 **Obiettivo:** {current_scenario['obiettivo_vendita']}")

if st.sidebar.button("🔄 Nuova Sessione"):
    st.session_state.messages = []
    st.rerun()

st.title(f"Simulazione: {scenario_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# --- 6. CHAT LOGIC (CORRETTA PER GEMINI) ---

user_input = st.chat_input("Consiglia il paziente...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Il cliente risponde..."):
        try:
            # Costruiamo il prompt completo includendo la storia per Gemini
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            full_instruction = f"""
            {current_scenario['prompt_cliente']} 
            Rispondi in italiano, max 2 frasi.
            Storia conversazione:
            {history_text}
            """
            
            # Chiamata diretta (più stabile della modalità chat)
            response = model.generate_content(full_instruction)
            ai_response = response.text

            # Audio
            asyncio.run(generate_audio(ai_response))
            with open("response.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()

        except Exception as e:
            st.error(f"Errore tecnico Gemini: {e}")

# --- 7. IL GIUDICE ---

if len(st.session_state.messages) > 1:
    st.divider()
    if st.button("🏁 VALUTA LA MIA VENDITA"):
        with st.spinner("Analisi in corso..."):
            chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
            
            judge_prompt = f"""
            Analizza questa vendita farmaceutica. Scenario: {scenario_name}.
            Restituisci SOLO un JSON:
            {{ "score": 0-100, "margine_euro": 5-30, "feedback": "...", "consiglio": "..." }}
            \n\nTRASCRIZIONE:\n{chat_text}
            """
            
            try:
                res_ai = model.generate_content(judge_prompt)
                # Pulizia JSON per Gemini
                text_clean = res_ai.text.replace('```json', '').replace('```', '').strip()
                res = json.loads(text_clean)
                
                st.header("🏆 Report Finale")
                c1, c2 = st.columns(2)
                c1.metric("Punteggio", f"{res['score']}/100")
                c2.metric("Margine", f"€ {res['margine_euro']}")
                st.info(f"**Feedback:** {res['feedback']}")
                
                registra_simulazione(st.session_state.user_name, scenario_name, res['score'], res['margine_euro'])
                st.toast("Dati salvati!")
            except:
                st.error("Errore nell'analisi automatica.")

# --- 8. DASHBOARD ---

st.sidebar.divider()
if st.sidebar.checkbox("📊 Dashboard Admin"):
    st.title("BI Analytics")
    try:
        df = pd.read_csv("storico_performance.csv")
        st.metric("Margine Totale", f"€ {df['Margine_Potenziale'].sum()}")
        st.dataframe(df.sort_values(by="Data", ascending=False), use_container_width=True)
    except:
        st.info("Nessun dato registrato.")