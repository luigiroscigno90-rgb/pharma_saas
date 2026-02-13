import os
import streamlit as st
from groq import Groq # CAMBIO FONDAMENTALE
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts
import plotly.graph_objects as go

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI (Llama Edition)", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f8f9fa;}
    div[data-testid="stSidebar"] {background-color: #1e272e; color: white;}
    h1, h2, h3 {color: #1e272e;}
    .stChatInput {border-radius: 20px;}
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTORE AI (GROQ - LLAMA 3) ---
try:
    # Inizializza il client Groq
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Errore API Key. Assicurati di aver impostato GROQ_API_KEY nei secrets.")
    st.stop()

def get_ai_response(messages, model="llama-3.3-70b-versatile", temperature=0.7):
    """Funzione universale per chiamare Llama 3"""
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
            stream=False
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Errore AI: {e}"

# --- 3. DATABASE SCENARI ---
SCENARIOS = {
    "Dolore Articolare": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Maria, 68 anni.",
        "sintomo": "Ginocchio gonfio.",
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria, 68 anni. Sei diffidente. Hai male al ginocchio. Vuoi solo la crema. Accetti il collagene SOLO se il farmacista ti spiega che la crema toglie il dolore oggi, ma il collagene ripara la cartilagine per il futuro. Se non lo spiega bene, rifiuta. Rispondi in massimo 20 parole."
    },
    "Tosse Fumatore": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Luca, 35 anni.",
        "sintomo": "Tosse secca mattutina.",
        "obiettivo": "Vendere: Sciroppo + Spray Gola.",
        "sys_prompt": "Sei Luca, 35 anni, fumatore. Hai fretta. Vuoi solo lo sciroppo. Rifiuti tutto il resto. Accetti lo spray SOLO se ti dicono che crea una barriera protettiva contro il fumo. Rispondi scocciato e breve (max 15 parole)."
    },
    "Insonnia Stress": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Giulia, 42 anni.",
        "sintomo": "Risvegli notturni.",
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia, manager stressata. Vuoi un sonnifero forte. Il farmacista deve convincerti a prendere Melatonina e Magnesio spiegando l'effetto rilassante sul sistema nervoso. Se propone farmaci pesanti, dì che hai paura della dipendenza. Sii breve."
    },
     "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Marco, 50 anni.",
        "sintomo": "Bruciore post-prandiale.",
        "obiettivo": "Vendere: Antiacido + Probiotici.",
        "sys_prompt": "Sei Marco. Mangi male. Vuoi solo tamponare il bruciore. Compri i probiotici solo se ti spiegano che riequilibrano la digestione. Rispondi brevemente."
    },
    "Dermocosmesi": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Elena, 55 anni.",
        "sintomo": "Rughe e pelle spenta.",
        "obiettivo": "Vendere: Crema + Siero.",
        "sys_prompt": "Sei Elena. Esigente. Compri il siero solo se ti spiegano tecnicamente come veicola la crema in profondità. Rispondi in modo snob e breve."
    }
}

# --- 4. AUDIO & GRAFICI ---
async def text_to_speech(text, voice_id):
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save("temp_audio.mp3")
        return True
    except: return False

def autoplay_audio(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""<audio controls autoplay style="width: 100%; margin-top: 10px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
        st.markdown(md, unsafe_allow_html=True)

def plot_radar_chart(categories, values):
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='Skill'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
    return fig

# --- 5. UI PRINCIPALE ---
with st.sidebar:
    st.title("PharmaFlow ⚡")
    st.caption("Powered by Llama 3 & Groq")
    
    if "user" not in st.session_state:
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if p == st.secrets["APP_PASSWORD"]:
                st.session_state.user = u
                st.rerun()
        st.stop()
    
    st.success(f"Dr. {st.session_state.user}")
    selected_scenario = st.selectbox("Scenario:", list(SCENARIOS.keys()))
    hard_mode = st.toggle("🔥 Modalità Incubo", value=False)
    
    if st.button("🔄 Nuova Sessione", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

current_data = SCENARIOS[selected_scenario]
st.header(f"Simulazione: {selected_scenario}")
st.markdown(f"**Paziente:** {current_data['persona']} | **Obiettivo:** {current_data['obiettivo']}")

if "messages" not in st.session_state: st.session_state.messages = []

# Mostra Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.write(msg["content"])

# --- 6. LOGICA CHAT ---
user_input = st.chat_input("Scrivi la tua risposta...")

if user_input:
    # 1. Messaggio Utente
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)
    
    # 2. Generazione Risposta AI
    with st.spinner("Il paziente riflette..."):
        # Costruzione Messaggi per Llama
        # Inseriamo il System Prompt all'inizio, ogni volta
        messages_payload = [{"role": "system", "content": current_data['sys_prompt']}]
        
        if hard_mode:
             messages_payload[0]["content"] += " Sii MOLTO scortese, interrompi e lamentati del prezzo alto."

        # Aggiungiamo la cronologia
        messages_payload.extend(st.session_state.messages)
        
        # Chiamata a Groq
        ai_text = get_ai_response(messages_payload)
        
        # Audio
        asyncio.run(text_to_speech(ai_text, current_data['voice']))

    # 3. Output AI
    st.session_state.messages.append({"role": "assistant", "content": ai_text})
    with st.chat_message("assistant"):
        st.write(ai_text)
        autoplay_audio("temp_audio.mp3")

# --- 7. ANALISI (JUDGE) ---
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 ANALIZZA SESSIONE", type="primary"):
        with st.spinner("Analisi clinica e commerciale in corso..."):
            
            # Creiamo un prompt specifico per il "Giudice"
            # Usiamo Llama 3 70B che è molto bravo nel reasoning
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            judge_prompt = f"""
            Agisci come un Direttore Commerciale Farmaceutico esperto.
            Analizza questa transazione tra Farmacista e Paziente.
            
            SCENARIO: {selected_scenario}
            OBIETTIVO: {current_data['obiettivo']}
            
            Devi restituire UNICAMENTE un JSON valido con questo formato esatto, senza altro testo:
            {{
                "voto_empatia": (intero 1-10),
                "voto_tecnica": (intero 1-10),
                "voto_chiusura": (intero 1-10),
                "totale": (intero 0-100),
                "soldi": (intero stima euro),
                "feedback": "stringa breve",
                "frase_migliore": "stringa breve"
            }}
            
            CHAT DA ANALIZZARE:
            {history_text}
            """
            
            # Chiamata isolata per l'analisi
            messages_judge = [{"role": "user", "content": judge_prompt}]
            res_judge = get_ai_response(messages_judge, temperature=0.1) # Bassa temperatura per JSON preciso
            
            try:
                # Pulizia JSON (Llama a volte è chiacchierone)
                json_str = res_judge
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0]
                elif "```" in json_str:
                     json_str = json_str.split("```")[1].split("```")[0]
                
                data = json.loads(json_str.strip())
                
                # Visualizzazione
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.subheader("📊 Radar Competenze")
                    fig = plot_radar_chart(
                        ['Empatia', 'Tecnica', 'Chiusura'], 
                        [data['voto_empatia'], data['voto_tecnica'], data['voto_chiusura']]
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with c2:
                    st.subheader("📋 Report")
                    m1, m2 = st.columns(2)
                    m1.metric("Score", f"{data['totale']}/100")
                    m2.metric("Revenue", f"€ {data['soldi']}")
                    st.info(f"**Feedback:** {data['feedback']}")
                    st.success(f"**Consiglio:** \"{data['frase_migliore']}\"")
                    
                    # Salvataggio CSV
                    file = "kpi_db.csv"
                    new_row = {"Date": datetime.now(), "User": st.session_state.user, "Score": data['totale']}
                    try: pd.read_csv(file)._append(new_row, ignore_index=True).to_csv(file, index=False)
                    except: pd.DataFrame([new_row]).to_csv(file, index=False)

            except Exception as e:
                st.error(f"Errore nel parsing dell'analisi. Riprova. Dettaglio: {e}")
                st.write("Raw response:", res_judge)