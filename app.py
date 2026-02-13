import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts
import time

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI", page_icon="⚕️", layout="wide")

# CSS per look professionale (nasconde menu standard e pulisce l'interfaccia)
st.markdown("""
    <style>
    .stApp {background-color: #f8f9fa;}
    div[data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    h1 {color: #2c3e50; font-family: 'Helvetica', sans-serif;}
    .stChatInput {border-radius: 20px;}
    .css-1d391kg {padding-top: 1rem;}
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTORE AI AUTO-ADATTIVO (Non toccare, funziona) ---
def get_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name: return genai.GenerativeModel(m.name)
        return genai.GenerativeModel("gemini-1.5-flash") # Fallback
    except:
        st.error("Errore API Key. Controlla i settings.")
        st.stop()

model = get_model()

# --- 3. DATABASE SCENARI (Il Valore Vero) ---
SCENARIOS = {
    "Dolore Articolare (Cross-Sell)": {
        "icon": "🦵",
        "persona": "Maria, 68 anni. Pensionata, diffidente ma vuole stare bene.",
        "sintomo": "Dolore al ginocchio che peggiora con l'umidità.",
        "obiettivo": "Vendere: Crema FANS (richiesta) + Collagene (proposta).",
        "prompt": "Sei Maria. Hai male al ginocchio. Vuoi solo la crema Voltaren. Se il farmacista propone integratori, rispondi 'Non voglio pasticche inutili'. Accetti SOLO se ti spiegano che la crema toglie il dolore oggi, ma il collagene ripara l'articolazione per domani."
    },
    "Tosse e Fumo (Prevenzione)": {
        "icon": "🚬",
        "persona": "Luca, 35 anni. Manager, fuma 10 sigarette al giorno.",
        "sintomo": "Tosse secca stizzosa, specialmente la mattina.",
        "obiettivo": "Vendere: Sciroppo (richiesto) + Spray Barriera (proposta).",
        "prompt": "Sei Luca. Hai fretta. Chiedi uno sciroppo qualsiasi. Se ti propongono altro, dici 'Ho fretta'. Compri lo spray solo se ti dicono che crea una pellicola che protegge la gola dal fumo."
    },
    "Insonnia da Stress (Consiglio)": {
        "icon": "🌙",
        "persona": "Giulia, 42 anni. Avvocato, dorme 4 ore a notte.",
        "sintomo": "Mi sveglio alle 3 di notte e penso al lavoro.",
        "obiettivo": "Vendere: Melatonina Retard + Magnesio.",
        "prompt": "Sei Giulia. Sei esausta. Vuoi un sonnifero forte. Il farmacista deve convincerti a non prendere farmaci ma usare Melatonina e Magnesio per rilassare il sistema nervoso. Sii scettica."
    },
    "Reflusso Gastrico (High Ticket)": {
        "icon": "🔥",
        "persona": "Marco, 50 anni. Sovrappeso, mangia male.",
        "sintomo": "Bruciore di stomaco dopo i pasti.",
        "obiettivo": "Vendere: Alginati + Probiotici specifici.",
        "prompt": "Sei Marco. Hai bruciore. Vuoi solo il Maalox. Il farmacista deve spiegarti che il problema è la digestione e proporti dei probiotici per riequilibrare, oltre all'antiacido."
    },
    "Dermocosmesi Anti-Age (Luxury)": {
        "icon": "✨",
        "persona": "Elena, 55 anni. Cura molto l'aspetto.",
        "sintomo": "Vedo la pelle spenta e le rughe più marcate.",
        "obiettivo": "Vendere: Crema Giorno + Siero Concentrato (Upselling).",
        "prompt": "Sei Elena. Cerchi una crema miracolosa. Il farmacista deve prima venderti il Siero spiegando che 'veicola' la crema in profondità. Senza questa spiegazione tecnica, non compri."
    }
}

# --- 4. GESTIONE AUDIO MIGLIORATA ---
async def text_to_speech(text):
    try:
        # Usa una voce maschile o femminile in base allo scenario? Per ora standardizziamo su Elsa
        communicate = edge_tts.Communicate(text, "it-IT-ElsaNeural")
        await communicate.save("temp_audio.mp3")
        return True
    except:
        return False

def autoplay_audio(file_path: str):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        # HTML5 Audio Player visibile e con autoplay
        md = f"""
            <audio controls autoplay style="width: 100%; margin-top: 10px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)

# --- 5. LOGICA DI SALVATAGGIO ---
def save_kpi(user, scenario, score, revenue):
    file = "kpi_db.csv"
    record = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "User": user,
        "Scenario": scenario,
        "Score": score,
        "Revenue": revenue
    }
    try:
        df = pd.read_csv(file)
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    except:
        df = pd.DataFrame([record])
    df.to_csv(file, index=False)

# --- 6. INTERFACCIA UTENTE (UI) ---

# Sidebar: Login e Selezione
with st.sidebar:
    st.title("PharmaFlow 2.0")
    
    if "user" not in st.session_state:
        st.warning("🔒 Accesso Richiesto")
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if p == st.secrets["APP_PASSWORD"]:
                st.session_state.user = u
                st.rerun()
        st.stop()
    
    st.success(f"Bentornato, Dr. {st.session_state.user}")
    
    selected_scenario = st.selectbox("Seleziona Training:", list(SCENARIOS.keys()))
    current_data = SCENARIOS[selected_scenario]
    
    st.info(f"**Obiettivo:** {current_data['obiettivo']}")
    st.markdown("---")
    if st.button("🔄 Nuova Simulazione", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    # Mini Dashboard nella sidebar
    if st.checkbox("Mostra Statistiche"):
        try:
            df = pd.read_csv("kpi_db.csv")
            user_df = df[df['User'] == st.session_state.user]
            st.metric("Tuo Punteggio Medio", f"{int(user_df['Score'].mean())}/100")
            st.metric("Fatturato Generato", f"€ {int(user_df['Revenue'].sum())}")
        except:
            st.write("Nessun dato ancora.")

# Main Area
st.header(f"{current_data['icon']} {selected_scenario}")
st.markdown(f"**Paziente:** {current_data['persona']} | **Sintomo:** {current_data['sintomo']}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input Area
user_input = st.chat_input("Cosa rispondi al paziente?")

if user_input:
    # 1. Scrivi messaggio utente
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    
    # 2. Genera risposta AI
    with st.spinner("Il paziente sta riflettendo..."):
        try:
            # Costruzione Prompt Contestuale
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            system_instruction = f"""
            Sei {current_data['persona']}. 
            Comportamento: {current_data['prompt']}
            
            IMPORTANTE:
            - Rispondi in italiano colloquiale.
            - Sii breve (massimo 20 parole).
            - Se il farmacista ti convince, dì che lo compri.
            - Se è troppo insistente, infastidisciti.
            
            STORIA DELLA CHAT:
            {history_text}
            """
            
            response = model.generate_content(system_instruction)
            ai_text = response.text
            
            # 3. Gestione Audio
            asyncio.run(text_to_speech(ai_text))
            
        except Exception as e:
            ai_text = "Mi scusi, non ho capito. Può ripetere?"
            st.error(f"Errore: {e}")

    # 4. Mostra risposta e audio
    st.session_state.messages.append({"role": "assistant", "content": ai_text})
    with st.chat_message("assistant"):
        st.write(ai_text)
        autoplay_audio("temp_audio.mp3")

# --- 7. IL COACH (Analisi Finale) ---
if len(st.session_state.messages) > 2:
    st.divider()
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🏁 VALUTA", type="primary"):
            with st.spinner("Il Coach sta analizzando la performance..."):
                chat_txt = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
                
                coach_prompt = f"""
                Sei un Coach di Vendita Farmaceutica.
                SCENARIO: {selected_scenario}
                OBIETTIVO: {current_data['obiettivo']}
                
                Analizza la chat.
                Restituisci SOLO un JSON:
                {{
                    "voto": (0-100),
                    "soldi_recuperati": (stima in euro del cross-selling, 0 se fallito),
                    "feedback_duro": "Critica diretta e onesta su cosa ha sbagliato.",
                    "frase_vincente": "La frase esatta che avrebbe dovuto dire."
                }}
                
                CHAT:
                {chat_txt}
                """
                
                try:
                    res = model.generate_content(coach_prompt)
                    clean_json = res.text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_json)
                    
                    st.success("Analisi Completata")
                    
                    # Visualizzazione Risultati "Card Style"
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Score", f"{data['voto']}/100")
                    c2.metric("Revenue", f"€ {data['soldi_recuperati']}")
                    c3.metric("Esito", "✅ VENDUTO" if data['voto'] > 75 else "❌ PERSO")
                    
                    st.warning(f"💡 **Feedback:** {data['feedback_duro']}")
                    st.info(f"🗣️ **Avresti dovuto dire:** \"{data['frase_vincente']}\"")
                    
                    save_kpi(st.session_state.user, selected_scenario, data['voto'], data['soldi_recuperati'])
                    
                except:
                    st.error("Errore nell'analisi. Riprova.")