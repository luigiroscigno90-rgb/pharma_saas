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
# Mostra il bottone solo se ci sono stati scambi nella chat
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 VALUTA LA MIA VENDITA"):
        with st.spinner("Il Coach sta analizzando la tua performance..."):
            
            # Creiamo il testo della conversazione
            chat_text = ""
            for msg in st.session_state.messages:
                chat_text += f"{msg['role'].upper()}: {msg['content']}\n"
            
            # Prompt Dinamico: Il giudice sa quale scenario stavi giocando
            judge_prompt = f"""
            Sei un Direttore Commerciale Farmaceutico.
            SCENARIO ATTIVO: {current_scenario['sintomo']}
            CLIENTE: {current_scenario['persona']}
            OBIETTIVO DI VENDITA (KPI): {current_scenario['obiettivo_vendita']}
            
            Analizza la seguente trascrizione della vendita.
            
            CRITERI DI VALUTAZIONE:
            1. PROTOCOLLO: Ha proposto TUTTI i prodotti dell'Obiettivo? (Sì/No)
            2. CROSS-SELLING: Ha spiegato il legame tra i prodotti?
            3. CHIUSURA: Ha chiesto esplicitamente l'acquisto?
            
            Output richiesto (JSON):
            {{
              "score": (voto 0-100),
              "feedback": "Commento tagliente su cosa manca.",
              "consiglio": "Frase esatta da usare la prossima volta."
            }}
            """
            
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": judge_prompt},
                        {"role": "user", "content": chat_text}
                    ],
                    temperature=0.2
                )
                analysis = completion.choices[0].message.content
                st.success("Analisi Completata")
                st.info(analysis)
            except Exception as e:
                st.error(f"Errore Analisi: {e}")