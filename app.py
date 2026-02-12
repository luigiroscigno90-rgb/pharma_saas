import streamlit as st
import os
from groq import Groq
import asyncio
import edge_tts
import pandas as pd
from datetime import datetime
import json
import base64

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

def check_password():
    """Ritorna True se l'utente è autorizzato"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    # Interfaccia grafica del Login
    st.set_page_config(page_title="PharmaFlow AI - Login", page_icon="🔒")
    
    st.title("🛡️ Accesso PharmaFlow AI")
    st.markdown("Inserisci le tue credenziali per iniziare l'allenamento.")
    
    with st.container():
        nome_utente = st.text_input("Nome e Cognome del Farmacista:")
        password = st.text_input("Password di Accesso:", type="password")
        
        if st.button("Accedi al Sistema"):
            # Controlliamo la password nei secrets
            if password == st.secrets["APP_PASSWORD"] and nome_utente.strip() != "":
                st.session_state.password_correct = True
                st.session_state.user_name = nome_utente.strip()
                st.rerun()
            elif nome_utente.strip() == "":
                st.warning("Per favore, inserisci il tuo nome.")
            else:
                st.error("Password errata o non autorizzata.")
    return False

# ESECUZIONE DEL BLOCCO LOGIN
if not check_password():
    st.stop() # Blocca il resto dell'app finché non si è loggati

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
            
            # --- AGGIUNTA VOCE ---
            async def speak(text):
                # Usiamo una voce femminile italiana naturale
                communicate = edge_tts.Communicate(text, "it-IT-ElsaNeural")
                await communicate.save("response.mp3")

            import asyncio
            asyncio.run(speak(ai_response))
            # ---------------------

            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            with st.chat_message("assistant"):
                st.write(ai_response)
                # Mostra il player audio sotto il testo
                # --- LOGICA AUDIO AUTOPLAY ---
            with open("response.mp3", "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode()
                md = f"""
                    <audio autoplay="true">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                    </audio>
                    """
                st.markdown(md, unsafe_allow_html=True)
            
            # Lasciamo comunque il widget visibile se l'utente vuole riascoltarlo
            st.audio("response.mp3", format="audio/mp3")
                
        except Exception as e:
            st.error(f"Errore AI: {e}")
# --- IL GIUDICE (ANALISI) ---
# Mostra il bottone solo se ci sono stati scambi nella chat
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 VALUTA LA MIA VENDITA"):
    if len(st.session_state.messages) < 2:
        st.warning("La conversazione è troppo breve per essere valutata.")
    else:
        with st.spinner("Il Coach sta analizzando la tua performance..."):
            
            # 1. Prepariamo il testo della conversazione
            chat_text = ""
            for msg in st.session_state.messages:
                chat_text += f"{msg['role'].upper()}: {msg['content']}\n"
            
            # 2. Prompt del Giudice (Aggiornato per includere il Margine)
            judge_prompt = f"""
            Sei un Direttore Commerciale Farmaceutico.
            SCENARIO ATTIVO: {current_scenario['sintomo']}
            OBIETTIVO DI VENDITA: {current_scenario['obiettivo_vendita']}
            
            Analizza la vendita e calcola il punteggio.
            
            Output richiesto (JSON STRETTO):
            {{
              "score": (0-100),
              "margine_euro": (stima il guadagno extra tra 5 e 30 se ha fatto cross-selling, altrimenti 0),
              "feedback": "Commento tagliente.",
              "consiglio": "Frase da usare."
            }}
            """
            
            try:
                # 3. Chiamata all'AI
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": judge_prompt},
                        {"role": "user", "content": chat_text}
                    ],
                    temperature=0.2
                )
                analysis = completion.choices[0].message.content
                
                # 4. Estrazione Dati dal JSON dell'AI
                # Pulizia per evitare che l'AI scriva testo inutile fuori dal JSON
                start_index = analysis.find('{')
                end_index = analysis.rfind('}') + 1
                json_str = analysis[start_index:end_index]
                res = json.loads(json_str)
                
                # 5. Visualizzazione Risultati
                st.success(f"Analisi Completata per {st.session_state.user_name}")
                col1, col2 = st.columns(2)
                col1.metric("Punteggio", f"{res['score']}/100")
                col2.metric("Margine Recuperato", f"€ {res['margine_euro']}")
                
                st.info(f"**Feedback:** {res['feedback']}")
                st.write(f"💡 **Consiglio:** {res['consiglio']}")

                # 6. SALVATAGGIO NEL DATABASE CSV
                registra_simulazione(
                    st.session_state.user_name,
                    scenario_name,
                    res['score'],
                    res['margine_euro']
                )
                st.toast("Dati salvati nella Dashboard!")

            except Exception as e:
                st.error(f"Errore durante l'analisi o il salvataggio: {e}")
                # In caso di errore nel JSON, mostriamo comunque la risposta grezza
                st.code(analysis)