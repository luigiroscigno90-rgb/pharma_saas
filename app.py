import streamlit as st
import os
from groq import Groq
import asyncio
import edge_tts

# --- CONFIGURAZIONE ---
try:
    # Prova a prendere la chiave dal cloud o dal file locale
    if "GROQ_API_KEY" in st.secrets:
        API_KEY = st.secrets["GROQ_API_KEY"]
    else:
        st.error("Chiave API mancante! Configura i secrets.")
        st.stop()
except FileNotFoundError:
    st.error("File secrets.toml non trovato in locale.")
    st.stop()

client = Groq(api_key=API_KEY)

# --- SCENARI (Il database dei casi clinici) ---
SCENARIOS = {
    "Dolore Ginocchio 🦵": {
        "persona": "Maria, 65 anni, diffidente.",
        "sintomo": "Dolore al ginocchio che non passa.",
        "obiettivo_vendita": "Protocollo: Crema Antinfiammatoria + Collagene Idrolizzato.",
        "prompt_cliente": "Sei Maria. Hai male al ginocchio. Sei tirchia. Se ti propongono solo la crema, dì che non basta. Se ti spiegano che il Collagene rigenera la cartilagine, accettalo."
    },
    "Tosse Secca 😷": {
        "persona": "Luca, 30 anni, fumatore, ha fretta.",
        "sintomo": "Tosse stizzosa che non mi fa dormire.",
        "obiettivo_vendita": "Protocollo: Sciroppo Sedativo + Spray Gola Protettivo.",
        "prompt_cliente": "Sei Luca. Hai fretta. Vuoi solo che la tosse smetta. Se il farmacista ti dà lo sciroppo, chiedi: 'Ma funziona subito?'. Se ti propone lo spray per proteggere la mucosa, dì 'Ok dammelo basta che funzioni'."
    },
    "Insonnia da Stress 🌙": {
        "persona": "Giulia, 40 anni, manager stressata.",
        "sintomo": "Mi sveglio alle 3 di notte e non riprendo sonno.",
        "obiettivo_vendita": "Protocollo: Melatonina Retard + Magnesio.",
        "prompt_cliente": "Sei Giulia. Sei ansiosa. Non vuoi sonniferi forti. Cerchi qualcosa di naturale ma potente. Se ti propongono solo la melatonina, dì 'L'ho già presa e non fa nulla'. Se aggiungono il Magnesio per il rilassamento muscolare, convinci."
    }
}

# --- INTERFACCIA ---
st.set_page_config(page_title="PharmaFlow Coach V2", page_icon="💊")

# BARRA LATERALE (Il Selettore)
st.sidebar.title("🩺 Cartella Clinica")
scenario_name = st.sidebar.selectbox("Scegli il Caso del Giorno:", list(SCENARIOS.keys()))
current_scenario = SCENARIOS[scenario_name]

st.sidebar.markdown(f"**Paziente:** {current_scenario['persona']}")
st.sidebar.markdown(f"**Sintomo:** {current_scenario['sintomo']}")
st.sidebar.info(f"🎯 **Obiettivo:** {current_scenario['obiettivo_vendita']}")

if st.sidebar.button("🔄 Riavvia Caso"):
    st.session_state.messages = []
    st.rerun()

# --- LOGICA AI ---
st.title(f"Simulazione: {scenario_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostra chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Input
user_input = st.chat_input("Scrivi la tua risposta...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Genera Risposta
    with st.spinner(f"{current_scenario['persona'].split(',')[0]} sta rispondendo..."):
        try:
            # Costruiamo il prompt dinamico in base allo scenario scelto
            sys_prompt = f"""
            {current_scenario['prompt_cliente']}
            Rispondi in italiano, brevemente (max 2 frasi).
            """
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.messages,
                temperature=0.7
            )
            ai_response = completion.choices[0].message.content
            
            # Audio (Opzionale - se dà errore lo saltiamo silenziosamente)
            # asyncio.run(...) qui semplificato per stabilità
            
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            with st.chat_message("assistant"):
                st.write(ai_response)
                
        except Exception as e:
            st.error(f"Errore AI: {e}")

# --- IL GIUDICE (ANALISI) ---
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 VALUTA LA MIA VENDITA"):
        with st.spinner("Analisi in corso..."):
            judge_prompt = f"""
            Sei un coach di vendita.
            SCENARIO: {current_scenario['sintomo']}
            OBIETTIVO: {current_scenario['obiettivo_vendita']}
            
            Analizza la chat. Il farmacista ha proposto TUTTI i prodotti dell'obiettivo?
            Ha spiegato il beneficio?
            
            Dai un voto 0-100 e un consiglio pratico.
            """
            # (Qui andrebbe la chiamata al giudice, per ora simuliamo per brevità di codice)
            # Per l'MVP V2, aggiungeremo la chiamata reale nel prossimo step.
            st.info("Funzione Analisi in aggiornamento per il supporto multi-scenario.")