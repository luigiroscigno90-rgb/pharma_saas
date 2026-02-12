import streamlit as st
import os
from groq import Groq
import asyncio
import edge_tts

# --- CONFIGURAZIONE ---
# ⚠️ INCOLLA QUI LA TUA CHIAVE (Mantieni le virgolette!)
# Recupera la chiave dai segreti di Streamlit (Cloud o Locale)
try:
    API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("Manca la API Key! Configurala nei secrets.")
    st.stop()

client = Groq(api_key=API_KEY)

# --- PROMPT DI SISTEMA (Il Cliente) ---
SYSTEM_PROMPT_MARIA = """
Sei 'Maria', 65 anni. Hai dolore al ginocchio.
Sei diffidente. Vuoi spendere poco.
1. Se il farmacista saluta, rispondi lamentandoti del dolore.
2. Se propone solo una crema, dì che non funziona.
3. Se propone un 'Protocollo completo' (es. crema + integratore) e spiega i benefici, accettalo.
4. Sii breve.
"""

# --- PROMPT DI ANALISI (Il Giudice) ---
SYSTEM_PROMPT_JUDGE = """
Sei un Direttore Commerciale Farmaceutico esperto.
Analizza la transazione del farmacista.

IL TUO OBIETTIVO:
Identificare se il farmacista ha applicato il protocollo "Cross-Category".
Per il mal di ginocchio (Dolore Articolare), il protocollo aureo è:
1. TOPICO (Crema/Gel) -> Per sollievo immediato.
2. SISTEMICO (Integratore Collagene/Glucosamina) -> Per cura a lungo termine.
3. GASTRO-PROTEZIONE (Se il cliente prende FANS orali).

Output richiesto (JSON strict):
{
  "score": (0-100),
  "analisi_cross_selling": "Hai proposto solo il Topico. Manca il Sistemico.",
  "occasione_mancata": "Potevi aggiungere 'Per non avere male tra un mese, le consiglio anche...'",
  "loss_revenue": "Stima perdita: -25€ (Mancata vendita integratore)."
}
Sii breve, diretto e focalizzato sui soldi persi.
"""

# --- FUNZIONI ---

async def generate_audio(text):
    communicate = edge_tts.Communicate(text, "it-IT-ElsaNeural")
    await communicate.save("risposta_maria.mp3")

def get_ai_response(messages):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT_MARIA}] + messages,
            temperature=0.7,
            max_tokens=150
        )
        return completion.choices[0].message.content
    except Exception as e:
        return "Errore connessione AI."

def analyze_performance(chat_history):
    """Invia tutta la chat al Giudice per il voto finale"""
    # Convertiamo la chat in un testo leggibile per il giudice
    conversation_text = ""
    for msg in chat_history:
        conversation_text += f"{msg['role'].upper()}: {msg['content']}\n"

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_JUDGE},
                {"role": "user", "content": conversation_text}
            ],
            temperature=0.2 # Bassa temperatura per essere precisi
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Errore Analisi: {e}"

# --- INTERFACCIA UTENTE ---

st.set_page_config(page_title="PharmaFlow Coach", page_icon="💊")

st.sidebar.title("Comandi Simulazione")
if st.sidebar.button("🔄 Nuova Simulazione"):
    st.session_state.messages = []
    st.rerun()

st.title("💊 PharmaFlow Coach")
st.markdown("Obiettivo: **Vendere il Protocollo Ginocchio (Crema + Collagene)**.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat Interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Input Farmacista
user_input = st.chat_input("Scrivi la tua risposta...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Maria risponde..."):
        ai_response = get_ai_response(st.session_state.messages)
        asyncio.run(generate_audio(ai_response))

    st.session_state.messages.append({"role": "assistant", "content": ai_response})
    with st.chat_message("assistant"):
        st.write(ai_response)
        st.audio("risposta_maria.mp3", format="audio/mp3", autoplay=True)

# SEZIONE ANALISI (Il Bottone Magico)
if len(st.session_state.messages) > 2: # Appare solo dopo 2 scambi
    st.divider()
    if st.button("🏁 TERMINA E VALUTA PERFORMANCE"):
        with st.spinner("Il Coach sta analizzando la tua vendita..."):
            analysis = analyze_performance(st.session_state.messages)
            st.success("Analisi Completata")
            st.markdown(f"### 📊 Report del Coach:\n{analysis}")