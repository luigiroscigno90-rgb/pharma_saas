import os
import streamlit as st
from groq import Groq
import pandas as pd
from datetime import datetime
import json
import base64
import asyncio
import edge_tts
import plotly.graph_objects as go

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI Tutor", page_icon="🎓", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f0f2f6;}
    div[data-testid="stSidebar"] {background-color: #1a252f; color: white;}
    .stChatInput {border-radius: 20px;}
    .stButton button {border-radius: 10px; font-weight: bold;}
    /* Stile per il tasto Suggerimento */
    div.stButton > button:first-child {
        background-color: #ffffff;
        color: #1a252f;
        border: 1px solid #1a252f;
    }
    div.stButton > button:active {
        background-color: #e8f0fe;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTORE AI (GROQ) ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Manca la GROQ_API_KEY nei secrets!")
    st.stop()

def get_ai_response(messages, temp=0.7, json_mode=False):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temp,
            max_tokens=1024,
            response_format={"type": "json_object"} if json_mode else None
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Errore AI: {e}"

# --- 3. DATABASE SCENARI ---
SCENARIOS = {
    "Dolore Articolare": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Maria, 68 anni.",
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria, 68 anni. Diffidente. Hai male al ginocchio. Vuoi solo la crema. Accetti il collagene SOLO se il farmacista ti spiega che la crema toglie il dolore oggi, ma il collagene ripara la cartilagine per il futuro. Rispondi in max 20 parole."
    },
    "Tosse Fumatore": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Luca, 35 anni.",
        "obiettivo": "Vendere: Sciroppo + Spray Gola.",
        "sys_prompt": "Sei Luca, 35 anni, fumatore. Hai fretta. Accetti lo spray SOLO se ti dicono che crea una barriera protettiva contro il fumo. Sii sbrigativo. Rispondi in max 15 parole."
    },
    "Insonnia Stress": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Giulia, 42 anni.",
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia, manager stressata. Vuoi farmaci forti. Accetti integratori SOLO se ti spiegano l'azione rilassante sul sistema nervoso. Sii scettica."
    },
     "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Marco, 50 anni.",
        "obiettivo": "Vendere: Antiacido + Probiotici.",
        "sys_prompt": "Sei Marco. Mangi male. Vuoi solo tamponare il bruciore. Compri i probiotici solo se ti spiegano che riequilibrano la digestione."
    },
    "Dermocosmesi Luxury": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Elena, 55 anni.",
        "obiettivo": "Vendere: Crema + Siero.",
        "sys_prompt": "Sei Elena. Esigente. Compri il siero solo se ti spiegano tecnicamente come veicola la crema in profondità."
    }
}

# --- 4. FUNZIONI UTILI ---
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
        md = f"""<audio controls autoplay style="width: 100%; margin-top: 5px;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
        st.markdown(md, unsafe_allow_html=True)

def plot_radar(values):
    categories = ['Empatia', 'Tecnica', 'Chiusura', 'Ascolto', 'Obiezioni']
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='Tu'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, margin=dict(t=20, b=20, l=40, r=40))
    return fig

# --- 5. SIDEBAR & SESSION STATE ---
if "user" not in st.session_state:
    st.session_state.user = "Guest"
if "history_scores" not in st.session_state:
    st.session_state.history_scores = []

with st.sidebar:
    st.title("PharmaFlow Tutor")
    st.caption("Powered by Llama 3 & Groq")
    
    selected_scenario = st.selectbox("Scenario:", list(SCENARIOS.keys()))
    hard_mode = st.toggle("🔥 Hard Mode", value=False)
    
    st.divider()
    
    # Progress Bar della sessione
    if st.session_state.history_scores:
        avg_score = sum(st.session_state.history_scores) / len(st.session_state.history_scores)
        st.metric("Media Sessione", f"{int(avg_score)}/100")
        st.progress(int(avg_score)/100)
    
    if st.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- 6. MAIN CHAT INTERFACE ---
current_data = SCENARIOS[selected_scenario]
st.header(f"🎓 Training: {selected_scenario}")
st.markdown(f"**Paziente:** {current_data['persona']} | **Obiettivo:** {current_data['obiettivo']}")

if "messages" not in st.session_state: st.session_state.messages = []

# Mostra Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.write(msg["content"])

# AREA SUGGERIMENTI (Il Tutor)
col_hint, col_space = st.columns([1, 4])
with col_hint:
    if st.button("💡 Suggeriscimi cosa dire"):
        with st.spinner("Il tutor sta pensando..."):
            hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            hint_prompt = [{"role": "system", "content": f"Sei un formatore esperto. L'obiettivo è: {current_data['obiettivo']}. Leggi la chat e suggerisci al farmacista una frase breve ed efficace per convincere il cliente ORA. Rispondi solo con la frase."},
                           {"role": "user", "content": f"Chat finora:\n{hist}"}]
            hint = get_ai_response(hint_prompt)
            st.toast(f"Tip: {hint}", icon="💡")
            st.info(f"**Tutor:** Prova a dire: *{hint}*")

# INPUT UTENTE
user_input = st.chat_input("Scrivi la tua risposta...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.write(user_input)
    
    with st.spinner("Il paziente risponde..."):
        # Logica Chat
        sys_prompt = current_data['sys_prompt']
        if hard_mode: sys_prompt += " Sii scontroso, interrompi, lamentati dei prezzi."
        
        msgs = [{"role": "system", "content": sys_prompt}] + st.session_state.messages
        ai_reply = get_ai_response(msgs)
        
        asyncio.run(text_to_speech(ai_reply, current_data['voice']))

    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
    with st.chat_message("assistant"):
        st.write(ai_reply)
        autoplay_audio("temp_audio.mp3")

# --- 7. ANALISI FINALE (PROFESSIONALE) ---
if len(st.session_state.messages) > 2:
    st.divider()
    if st.button("🏁 TERMINA E VALUTA", type="primary", use_container_width=True):
        with st.spinner("Generazione Report Avanzato..."):
            hist_txt = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            # Prompt Analitico Complesso (JSON Mode)
            judge_prompt = f"""
            Analizza questa vendita farmaceutica.
            SCENARIO: {selected_scenario}
            OBIETTIVO: {current_data['obiettivo']}
            
            Restituisci JSON puro:
            {{
                "score_empatia": (1-10),
                "score_tecnica": (1-10),
                "score_chiusura": (1-10),
                "score_ascolto": (1-10),
                "score_obiezioni": (1-10),
                "totale": (0-100),
                "revenue": (stima euro),
                "feedback_main": "Breve commento generale",
                "mistake": "L'errore più grave commesso",
                "correction": "Cosa avrebbe dovuto dire invece",
                "best_moment": "Il momento migliore della chat"
            }}
            
            CHAT:
            {hist_txt}
            """
            
            res_json = get_ai_response([{"role": "user", "content": judge_prompt}], json_mode=True)
            
            try:
                data = json.loads(res_json)
                st.session_state.history_scores.append(data['totale'])
                
                # --- LAYOUT REPORT A SCHEDE ---
                st.balloons()
                st.subheader("📊 Report di Performance")
                
                tab1, tab2, tab3 = st.tabs(["📈 Overview", "🧠 Analisi Tattica", "📝 Trascrizione"])
                
                with tab1:
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        # Radar Chart
                        vals = [data['score_empatia'], data['score_tecnica'], data['score_chiusura'], 
                                data['score_ascolto'], data['score_obiezioni']]
                        st.plotly_chart(plot_radar(vals), use_container_width=True)
                    with c2:
                        st.metric("Punteggio Finale", f"{data['totale']}/100")
                        st.metric("Fatturato Stimato", f"€ {data['revenue']}")
                        if data['totale'] > 75:
                            st.success("✅ OBIETTIVO RAGGIUNTO")
                        else:
                            st.error("❌ VENDITA FALLITA")

                with tab2:
                    st.info(f"**Feedback Generale:** {data['feedback_main']}")
                    
                    col_err, col_corr = st.columns(2)
                    with col_err:
                        st.error("🚫 **L'Errore:**")
                        st.write(data['mistake'])
                    with col_corr:
                        st.success("✨ **La Correzione:**")
                        st.write(data['correction'])
                    
                    st.write(f"🌟 **Punto di Forza:** {data['best_moment']}")

                with tab3:
                    st.text_area("Log Chat", hist_txt, height=300)

            except Exception as e:
                st.error("Errore analisi JSON. Riprova.")