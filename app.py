import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts

# --- 1. CONFIGURAZIONE MOTORE ELITE ---
st.set_page_config(page_title="PharmaFlow AI Pro", page_icon="💊", layout="wide")

# Forza l'uso dell'API stabile
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # Usiamo il nome 1.5-flash: è lo stesso "motore" che Gemini 3 usa per la velocità, 
    # ma con il nome compatibile per la libreria 0.8.6
    model = genai.GenerativeModel('gemini-1.5-flash') 
except Exception as e:
    st.error(f"⚠️ Errore critico configurazione: {e}")
    st.stop()

# --- 2. LOGICA DI STORAGE E ASSETS ---

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
    # Elsa è professionale e chiara per l'ambiente farmacia
    communicate = edge_tts.Communicate(text, "it-IT-ElsaNeural")
    await communicate.save("response.mp3")

# --- 3. SECURITY GATE ---

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
                st.error("Accesso negato. Credenziali non valide.")
    return False

if not check_password():
    st.stop()

# --- 4. SCENARI AD ALTO MARGINE ---

SCENARIOS = {
    "Dolore Ginocchio 🦵": {
        "persona": "Maria, 65 anni, diffidente.",
        "obiettivo_vendita": "Protocollo: Crema Antinfiammatoria + Ciclo Collagene.",
        "prompt_cliente": "Sei Maria. Sei stanca del dolore ma non vuoi 'buttare soldi'. Accetti il collagene solo se il farmacista è autorevole e spiega che la crema cura il sintomo, ma il collagene rigenera la cartilagine."
    },
    "Tosse Secca 😷": {
        "persona": "Luca, 30 anni, fumatore, frettoloso.",
        "obiettivo_vendita": "Protocollo: Sciroppo Sedativo + Spray Gola Protettivo.",
        "prompt_cliente": "Sei Luca. Hai fretta. Vuoi solo lo sciroppo. Rifiuti lo spray a meno che non ti spieghino che il fumo ha rimosso la protezione naturale della gola e lo spray la ripristina."
    },
    "Insonnia 🌙": {
        "persona": "Giulia, 40 anni, manager stressata.",
        "obiettivo_vendita": "Protocollo: Melatonina Retard + Magnesio Supremo.",
        "prompt_cliente": "Sei Giulia. Dormi male ma hai paura di 'rimanere rintontita' al mattino. Accetti il magnesio solo se ti spiegano l'azione biochimica sul sistema nervoso."
    }
}

# --- 5. INTERFACCIA DI ALLENAMENTO ---

st.sidebar.title(f"👨‍⚕️ Dr. {st.session_state.user_name}")
scenario_name = st.sidebar.selectbox("Caso Clinico:", list(SCENARIOS.keys()))
current_scenario = SCENARIOS[scenario_name]

st.sidebar.markdown(f"**Paziente:** {current_scenario['persona']}")
st.sidebar.info(f"🎯 **KPI Obiettivo:** {current_scenario['obiettivo_vendita']}")

if st.sidebar.button("🔄 Reset Simulazione"):
    st.session_state.messages = []
    st.rerun()

st.title(f"Simulazione: {scenario_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversazione
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# --- 6. LOGICA CHAT GEMINI 3 FLASH ---

user_input = st.chat_input("Digita il tuo consiglio professionale...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Il cliente analizza la proposta..."):
        try:
            # Storia per contesto
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            # Prompt ingegnerizzato per Gemini 3
            prompt_engine = f"""
            {current_scenario['prompt_cliente']}
            Rispondi in modo realistico, breve (max 2 frasi) e con il tono del paziente descritto.
            
            STORICO CONVERSAZIONE:
            {history_text}
            """
            
            response = model.generate_content(prompt_engine)
            ai_response = response.text

            # Generazione Audio Real-time
            asyncio.run(generate_audio(ai_response))
            with open("response.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()

        except Exception as e:
            st.error(f"⚠️ Errore di comunicazione AI: {e}")

# --- 7. IL GIUDICE COMMERCIALE (ANALISI AVANZATA) ---

if len(st.session_state.messages) > 1:
    st.divider()
    if st.button("🏁 ANALIZZA PERFORMANCE E CHIUDI VENDITA"):
        with st.spinner("Il Direttore Commerciale sta valutando la sessione..."):
            chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
            
            judge_prompt = f"""
            Sei un esperto di vendite in farmacia. Analizza questa trascrizione.
            SCENARIO: {scenario_name}
            OBIETTIVO: {current_scenario['obiettivo_vendita']}
            
            Analizza rigore scientifico, empatia e chiusura commerciale.
            
            RESTITUISCI SOLO JSON PURO:
            {{
                "score": 0-100,
                "margine_euro": 5-40,
                "feedback": "Analisi tagliente della performance.",
                "consiglio": "Script esatto da usare per chiudere la prossima volta."
            }}
            
            TRASCRIZIONE:
            {chat_text}
            """
            
            try:
                res_ai = model.generate_content(judge_prompt)
                # Pulizia JSON aggressiva
                json_clean = res_ai.text.replace('```json', '').replace('```', '').strip()
                res = json.loads(json_clean)
                
                # Visualizzazione Risultati
                st.balloons()
                st.header("📊 Verdetto Strategico")
                col1, col2 = st.columns(2)
                col1.metric("Punteggio Vendita", f"{res['score']}/100")
                col2.metric("Margine Recuperato", f"€ {res['margine_euro']}")
                
                with st.expander("Vedi Analisi Dettagliata", expanded=True):
                    st.write(f"**Feedback:** {res['feedback']}")
                    st.success(f"**Script d'Oro:** {res['consiglio']}")
                
                registra_simulazione(st.session_state.user_name, scenario_name, res['score'], res['margine_euro'])
                
            except Exception as e:
                st.error(f"Errore nell'analisi del verdetto: {e}")

# --- 8. DASHBOARD ANALYTICS ---

st.sidebar.divider()
if st.sidebar.checkbox("📈 Dashboard Titolare"):
    st.title("📊 Business Intelligence Farmacia")
    try:
        df = pd.read_csv("storico_performance.csv")
        
        # Statistiche di alto livello
        m1, m2 = st.columns(2)
        m1.metric("Margine Totale Stimato", f"€ {df['Margine_Potenziale'].sum()}")
        m2.metric("Rating Medio Team", f"{int(df['Punteggio'].mean())}/100")
        
        st.subheader("Storico Performance Collaboratori")
        st.dataframe(df.sort_values(by="Data", ascending=False), use_container_width=True)
        
        st.subheader("Trend Miglioramento")
        st.line_chart(df.set_index("Data")["Punteggio"])
    except:
        st.info("Nessun dato ancora disponibile. Inizia la prima simulazione.")