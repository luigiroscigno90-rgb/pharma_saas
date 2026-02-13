import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts
import plotly.graph_objects as go # NUOVO: Per i grafici radar

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI Pro", page_icon="💊", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f8f9fa;}
    div[data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    h1, h2, h3 {color: #2c3e50; font-family: 'Helvetica', sans-serif;}
    .stMetric {background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);}
    div[data-testid="stExpander"] {background-color: white; border-radius: 10px;}
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTORE AI ---
def get_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name: return genai.GenerativeModel(m.name)
        return genai.GenerativeModel("gemini-1.5-flash")
    except:
        st.error("Errore API Key.")
        st.stop()

model = get_model()

# --- 3. DATABASE SCENARI ---
SCENARIOS = {
    "Dolore Articolare": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Maria, 68 anni.",
        "sintomo": "Ginocchio gonfio.",
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "prompt": "Sei Maria. Diffidente. Vuoi solo la crema. Accetti il collagene solo se spiegano che rigenera la cartilagine."
    },
    "Tosse Fumatore": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Luca, 35 anni.",
        "sintomo": "Tosse secca.",
        "obiettivo": "Vendere: Sciroppo + Spray Gola.",
        "prompt": "Sei Luca. Hai fretta. Vuoi solo lo sciroppo. Compri lo spray solo se ti dicono che protegge dal fumo."
    },
    "Insonnia Stress": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Giulia, 42 anni.",
        "sintomo": "Risvegli notturni.",
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "prompt": "Sei Giulia. Esausta. Vuoi farmaci forti. Accetti integratori solo se ti spiegano l'azione rilassante muscolare."
    },
    "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Marco, 50 anni.",
        "sintomo": "Bruciore post-prandiale.",
        "obiettivo": "Vendere: Antiacido + Probiotici.",
        "prompt": "Sei Marco. Mangi male. Vuoi solo tamponare il bruciore. Compri i probiotici solo se ti spiegano che riequilibrano la digestione."
    },
    "Dermocosmesi": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Elena, 55 anni.",
        "sintomo": "Rughe e pelle spenta.",
        "obiettivo": "Vendere: Crema + Siero.",
        "prompt": "Sei Elena. Esigente. Compri il siero solo se ti spiegano tecnicamente come veicola la crema in profondità."
    }
}

# --- 4. FUNZIONI AUDIO & GRAFICI ---
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
    fig = go.Figure(data=go.Scatterpolar(
      r=values,
      theta=categories,
      fill='toself',
      name='Performance'
    ))
    fig.update_layout(
      polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
      showlegend=False,
      margin=dict(l=20, r=20, t=20, b=20) # Margini ridotti
    )
    return fig

# --- 5. UI PRINCIPALE ---
with st.sidebar:
    st.title("PharmaFlow 3.0")
    if "user" not in st.session_state:
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            if p == st.secrets["APP_PASSWORD"]:
                st.session_state.user = u
                st.rerun()
        st.stop()
    
    st.success(f"👨‍⚕️ Dr. {st.session_state.user}")
    selected_scenario = st.selectbox("Scenario:", list(SCENARIOS.keys()))
    
    # NUOVO: HARD MODE
    hard_mode = st.toggle("🔥 Modalità Incubo", value=False)
    
    if st.button("🔄 Nuova Sessione", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # NUOVO: DOWNLOAD REPORT (Simulato)
    if st.button("📥 Scarica Report PDF"):
        st.toast("Generazione PDF in corso... (Feature in arrivo)")

current_data = SCENARIOS[selected_scenario]
st.header(f"Simulazione: {selected_scenario}")
st.markdown(f"**Paziente:** {current_data['persona']} | **Obiettivo:** {current_data['obiettivo']}")

if hard_mode:
    st.warning("⚠️ ATTENZIONE: Il cliente è in 'Hard Mode'. Sarà scontroso, interromperà e farà obiezioni sul prezzo.")

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.write(msg["content"])

user_input = st.chat_input("Scrivi la tua risposta...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)
    
    with st.spinner("Il paziente riflette..."):
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        
        # PROMPT DINAMICO (HARD MODE)
        mood = "Sei MOLTO scontroso, hai fretta e ti lamenti dei prezzi alti." if hard_mode else "Sei diffidente ma educato."
        
        system_instruction = f"""
        Sei {current_data['persona']}
        Atteggiamento: {mood}
        Istruzioni Scenario: {current_data['prompt']}
        
        Rispondi in italiano colloquiale (max 25 parole).
        STORIA CHAT: {history_text}
        """
        try:
            res = model.generate_content(system_instruction)
            ai_text = res.text
            asyncio.run(text_to_speech(ai_text, current_data['voice']))
        except Exception as e:
            ai_text = "..."
            st.error(e)

    st.session_state.messages.append({"role": "assistant", "content": ai_text})
    with st.chat_message("assistant"):
        st.write(ai_text)
        autoplay_audio("temp_audio.mp3")

# --- 6. ANALISI & RADAR CHART ---
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 ANALIZZA SESSIONE", type="primary"):
        with st.spinner("Calcolo metriche avanzate..."):
            chat_txt = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            # Prompt Analitico per il Radar
            coach_prompt = f"""
            Analizza la chat. Scenario: {selected_scenario}.
            Restituisci JSON STRETTO:
            {{
                "voto_empatia": (1-10),
                "voto_tecnica": (1-10),
                "voto_chiusura": (1-10),
                "totale": (0-100),
                "soldi": (stima euro),
                "feedback": "Commento breve",
                "frase_migliore": "Script corretto"
            }}
            CHAT: {chat_txt}
            """
            try:
                res = model.generate_content(coach_prompt)
                clean = res.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean)
                
                # Layout a colonne: Grafico a Sinistra, Dati a Destra
                c1, c2 = st.columns([1, 1])
                
                with c1:
                    st.subheader("📊 Radar Competenze")
                    fig = plot_radar_chart(
                        ['Empatia', 'Tecnica', 'Chiusura'], 
                        [data['voto_empatia'], data['voto_tecnica'], data['voto_chiusura']]
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with c2:
                    st.subheader("📋 Report Finale")
                    m1, m2 = st.columns(2)
                    m1.metric("Score Totale", f"{data['totale']}/100")
                    m2.metric("Revenue", f"€ {data['soldi']}")
                    
                    st.info(f"**Feedback:** {data['feedback']}")
                    st.success(f"**Consiglio:** \"{data['frase_migliore']}\"")
                    
                    # Salvataggio CSV (Nascosto)
                    file = "kpi_db.csv"
                    new_row = {"Date": datetime.now(), "User": st.session_state.user, "Score": data['totale']}
                    try: pd.read_csv(file)._append(new_row, ignore_index=True).to_csv(file, index=False)
                    except: pd.DataFrame([new_row]).to_csv(file, index=False)

            except Exception as e:
                st.error(f"Errore Analisi: {e}")