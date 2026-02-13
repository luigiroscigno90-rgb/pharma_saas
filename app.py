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
import plotly.express as px
import hashlib
from streamlit_mic_recorder import mic_recorder # NUOVO: Libreria per il microfono
import io # NUOVO: Per gestire i file audio in memoria

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="PharmaFlow AI Suite", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f4f6f9;}
    div[data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    .stMetric {background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    h1, h2, h3 {color: #2c3e50;}
    /* Tabella Admin più leggibile */
    .dataframe {font-size: 14px !important;}
    /* Stile bottone microfono */
    button[kind="secondary"] {border-radius: 50px; border: 1px solid #ddd; height: 3rem;}
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTH SYSTEM (Password Hashing) ---
DB_FILE = "users_db.json"
KPI_FILE = "kpi_db.csv"
ADMIN_PASS = "admin123"

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def load_users():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r") as f: return json.load(f)

def save_user(username, password, name, gender):
    users = load_users()
    if username in users: return False
    users[username] = {
        "password": make_hashes(password),
        "name": name, 
        "gender": gender,
        "avatar": "👨‍⚕️" if gender == "Uomo" else "👩‍⚕️"
    }
    with open(DB_FILE, "w") as f: json.dump(users, f)
    return True

def login_user(username, password):
    users = load_users()
    if username in users and check_hashes(password, users[username]['password']):
        return users[username]
    return None

# --- 3. MOTORE AI (GROQ) ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("⚠️ GROQ_API_KEY mancante!")
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

# NUOVO: Funzione per trascrivere audio con Groq Whisper
def transcribe_audio(audio_bytes):
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav" 
        transcription = client.audio.transcriptions.create(
            file=(audio_file.name, audio_file.read()),
            model="whisper-large-v3",
            response_format="text",
            language="it"
        )
        return transcription
    except Exception as e:
        st.error(f"Errore Trascrizione: {e}")
        return None

# --- 4. DATA & SCENARIOS ---
SCENARIOS = {
    # --- 1. DOLORE E INFIAMMAZIONE (4 Casi) ---
    "Dolore Articolare (Anziano)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Maria, 70 anni, pensionata.", 
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria. Hai male al ginocchio. Vuoi solo il Voltaren. Rifiuti il collagene perché 'sono solo integratori'. Accetti SOLO se ti spiegano che la crema spegne il dolore oggi, ma il collagene ripara la cartilagine per domani. Max 20 parole."
    },
    "Cervicale e Stress (Lavoratore)": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Marco, 45 anni, videoterminalista.", 
        "obiettivo": "Vendere: Cerotti autoriscaldanti + Magnesio.",
        "sys_prompt": "Sei Marco. Hai il collo bloccato. Vuoi una pastiglia forte. Rifiuti il magnesio. Lo compri SOLO se ti spiegano che il dolore viene dai muscoli contratti e il magnesio serve a scioglierli. Max 20 parole."
    },
    "Mal di Testa (Donna)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Chiara, 30 anni, impiegata.", 
        "obiettivo": "Vendere: Ibuprofene (Moment) + Coadiuvante (Caffeina/Vit B).",
        "sys_prompt": "Sei Chiara. Hai un cerchio alla testa. Vuoi il solito farmaco. Il farmacista deve proporti una formula più specifica o un integratore per la stanchezza mentale. Se propone cose a caso, rifiuta. Max 15 parole."
    },
    "Trauma Sportivo (Giovane)": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Luca, 22 anni, calciatore.", 
        "obiettivo": "Vendere: Ghiaccio Spray + Arnica Alta Concentrazione.",
        "sys_prompt": "Sei Luca. Hai preso una botta. Vuoi solo il ghiaccio. Accetti l'Arnica solo se ti dicono che 'dimezza i tempi di recupero dell'ematoma'. Hai fretta di giocare. Max 15 parole."
    },

    # --- 2. GASTROINTESTINALE (4 Casi) ---
    "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Giuseppe, 55 anni, camionista.", 
        "obiettivo": "Vendere: Antiacido (Maalox) + Probiotici specifici.",
        "sys_prompt": "Sei Giuseppe. Mangi male. Hai bruciore. Vuoi solo tamponare. Compri i probiotici SOLO se ti spiegano che 'riparano la mucosa' e non curano solo il sintomo. Sii pratico. Max 20 parole."
    },
    "Gonfiore Addominale": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Simona, 35 anni, gonfia dopo i pasti.", 
        "obiettivo": "Vendere: Carbone/Simeticone + Enzimi Digestivi.",
        "sys_prompt": "Sei Simona. Ti senti un pallone. Chiedi carbone. Rifiuti gli enzimi per il prezzo. Accetti SOLO se ti spiegano che il carbone toglie l'aria presente, ma gli enzimi impediscono che si formi nuova aria. Max 20 parole."
    },
    "Terapia Antibiotica (Must)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Mamma Laura, 40 anni (per il figlio).", 
        "obiettivo": "Vendere: Antibiotico (Ricetta) + Fermenti Lattici.",
        "sys_prompt": "Sei Laura. Hai la ricetta dell'antibiotico. Rifiuti i fermenti dicendo 'ne ho già a casa'. Il farmacista deve chiederti se sono specifici per antibiotico e spiegarti che senza di essi al bambino verrà la diarrea. Max 20 parole."
    },
    "Stitichezza Occasionale": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Paolo, 60 anni.", 
        "obiettivo": "Vendere: Microclismi (Urgenza) + Fibre/Macrogol (Mantenimento).",
        "sys_prompt": "Sei Paolo. Sei bloccato da 3 giorni. Vuoi una purga forte subito. Il farmacista deve darti l'urgenza MA venderti anche le fibre per 'educare' l'intestino e non dipendere dai lassativi. Max 20 parole."
    },

    # --- 3. INVERNO E RESPIRATORIO (4 Casi) ---
    "Tosse Secca (Fumatore)": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Roberto, 50 anni, fumatore.", 
        "obiettivo": "Vendere: Sciroppo Sedativo + Spray Barriera.",
        "sys_prompt": "Sei Roberto. Tossi la mattina. Vuoi uno sciroppo qualsiasi. Rifiuti lo spray. Lo compri SOLO se il farmacista ti dice che crea un 'film protettivo' contro il catrame. Sii sbrigativo. Max 20 parole."
    },
    "Raffreddore e Naso Chiuso": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Anna, 28 anni.", 
        "obiettivo": "Vendere: Spray Decongestionante + Igiene Nasale (Acqua mare).",
        "sys_prompt": "Sei Anna. Naso tappato. Vuoi il Rinazina. Rifiuti i lavaggi nasali. Accetti SOLO se ti spiegano che lo spray libera, ma l'acqua di mare pulisce i virus e guarisci prima. Max 15 parole."
    },
    "Mal di Gola (Voce)": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Andrea, 30 anni, insegnante.", 
        "obiettivo": "Vendere: Spray Gola + Erisimo (per la voce).",
        "sys_prompt": "Sei Andrea. Hai la voce rauca. Vuoi caramelle. Accetti l'Erisimo solo se il farmacista specifica che 'ripristina il tono vocale' per fare lezione domani. Max 20 parole."
    },
    "Influenza (Prevenzione)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Signora Giovanna, 75 anni.", 
        "obiettivo": "Vendere: Tachipirina + Vitamina C/Zinco.",
        "sys_prompt": "Sei Giovanna. Hai paura dell'influenza. Compri la Tachipirina per sicurezza. Il farmacista deve venderti la prevenzione (Vit C/Zinco) spiegando che agli anziani le difese si abbassano. Max 25 parole."
    },

    # --- 4. BENESSERE E COSMESI (4 Casi - Alto Margine) ---
    "Insonnia e Stress": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Giulia, 42 anni, manager.", 
        "obiettivo": "Vendere: Melatonina + Magnesio.",
        "sys_prompt": "Sei Giulia. Dormi male. Vuoi un farmaco. Il farmacista deve convincerti a provare prima Melatonina e Magnesio spiegando l'azione sul sistema nervoso centrale. Sii scettica sui prodotti naturali. Max 20 parole."
    },
    "Stanchezza Fisica": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Luigi, 50 anni, spossato.", 
        "obiettivo": "Vendere: Polase (Sali) + Multivitaminico Completo.",
        "sys_prompt": "Sei Luigi. Ti senti fiacco. Chiedi il Polase (pubblicità). Il farmacista deve venderti un Multivitaminico completo (più costoso). Accetti solo se ti dice che 'i sali durano 2 ore, le vitamine ti coprono tutto il giorno'. Max 20 parole."
    },
    "Anti-Age Viso (Luxury)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Elena, 55 anni, curata.", 
        "obiettivo": "Vendere: Crema Giorno + Siero Concentrato.",
        "sys_prompt": "Sei Elena. Vuoi una crema miracolosa. Rifiuti il siero perché 'costa troppo'. Lo compri SOLO se il farmacista ti spiega che il siero è il 'veicolo' che porta la crema in profondità. Sii snob. Max 15 parole."
    },
    "Caduta Capelli (Stagionale)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Francesca, 35 anni, preoccupata.", 
        "obiettivo": "Vendere: Fiale Anticaduta + Integratore (In & Out).",
        "sys_prompt": "Sei Francesca. Perdi capelli. Vuoi le fiale. Rifiuti le pastiglie. Accetti l'integratore SOLO se ti spiegano che le fiale lavorano sul bulbo, ma l'integratore dà il 'materiale' (cheratina) per costruire il capello. Max 20 parole."
    },

    # --- 5. CASISTICHE SPECIALI (4 Casi) ---
    "Cistite (Urgenza)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Sara, 25 anni.", 
        "obiettivo": "Vendere: Monuril (Ricetta) + Fermenti/Cranberry.",
        "sys_prompt": "Sei Sara. Hai bruciore forte. Hai la ricetta. Rifiuti altro. Accetti il Cranberry o Probiotici SOLO se ti dicono che servono a evitare che la cistite torni tra un mese. Max 15 parole."
    },
    "Occhi Secchi (Schermi)": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Davide, 20 anni, gamer.", 
        "obiettivo": "Vendere: Collirio Ialuronico + Integratore Mirtillo.",
        "sys_prompt": "Sei Davide. Occhi rossi da PC. Vuoi un collirio economico. Rifiuti l'integratore. Lo compri SOLO se ti spiegano che il collirio bagna, ma l'integratore protegge la retina dalla luce blu. Max 20 parole."
    },
    "Gambe Pesanti (Estate)": {
        "voice": "it-IT-ElsaNeural", 
        "persona": "Rosa, 65 anni, sovrappeso.", 
        "obiettivo": "Vendere: Gel Freddo + Compresse Microcircolo.",
        "sys_prompt": "Sei Rosa. Caviglie gonfie. Vuoi il gel. Rifiuti le compresse perché 'prendo troppe medicine'. Accetti SOLO se ti spiegano che il gel dura poco, le compresse rinforzano le vene dall'interno. Max 20 parole."
    },
    "Colesterolo Borderline": {
        "voice": "it-IT-DiegoNeural", 
        "persona": "Mario, 58 anni.", 
        "obiettivo": "Vendere: Riso Rosso Fermentato + Coenzima Q10.",
        "sys_prompt": "Sei Mario. Il medico ha detto che hai il colesterolo un po' alto. Vuoi un integratore. Rifiuti il Coenzima Q10. Lo accetti SOLO se ti spiegano che il riso rosso abbassa il colesterolo ma può stancare i muscoli, e il Q10 ridà energia. Max 25 parole."
    }
}

# --- 5. FUNZIONI UTILI ---
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

# --- 6. DASHBOARD TITOLARE (ADMIN) ---
def render_admin_dashboard():
    st.title("📊 PharmaBoss Dashboard")
    st.markdown("Monitoraggio performance e ROI della formazione.")
    
    if not os.path.exists(KPI_FILE):
        st.warning("Nessun dato registrato. Fai fare la prima simulazione ai tuoi dipendenti!")
        return

    df = pd.read_csv(KPI_FILE)
    
    # 1. KPI GENERALI
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fatturato Potenziale", f"€ {df['Revenue'].sum()}")
    col2.metric("Media Voto Team", f"{int(df['Score'].mean())}/100")
    col3.metric("Simulazioni Totali", len(df))
    col4.metric("Farmacisti Attivi", df['User'].nunique())
    
    st.divider()
    
    # 2. CLASSIFICA (LEADERBOARD)
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("🏆 Top Performer")
        leaderboard = df.groupby('User').agg({'Score': 'mean', 'Revenue': 'sum', 'Scenario': 'count'}).reset_index()
        leaderboard.columns = ['Farmacista', 'Voto Medio', 'Fatturato Totale', 'N. Sessioni']
        leaderboard = leaderboard.sort_values(by='Fatturato Totale', ascending=False)
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
    with c2:
        st.subheader("📉 Aree Critiche")
        weakness = df.groupby('Scenario')['Score'].mean().sort_values()
        fig_bar = px.bar(weakness, x='Score', y=weakness.index, orientation='h', 
                         color='Score', color_continuous_scale='RdYlGn', title="Media Voto per Caso")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # 3. ANALISI SINGOLA (DRILL DOWN)
    st.subheader("🔎 Analisi Singolo Dipendente")
    selected_emp = st.selectbox("Seleziona Farmacista:", df['User'].unique())
    
    emp_df = df[df['User'] == selected_emp]
    
    # Grafico Andamento nel Tempo
    fig_line = px.line(emp_df, x=emp_df.index, y='Score', markers=True, title=f"Trend Miglioramento: {selected_emp}")
    st.plotly_chart(fig_line, use_container_width=True)
    
    # Ultimi Feedback negativi
    st.write("🛑 **Ultimi Errori Rilevati:**")
    st.table(emp_df[['Scenario', 'Score']].tail(5))

# --- 7. SIDEBAR LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

with st.sidebar:
    st.title("PharmaFlow")
    
    # LOGIN/LOGOUT
    if st.session_state.logged_in:
        user = st.session_state.user_info
        st.write(f"**{user['avatar']} {user['name']}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.divider()
    
    # ADMIN TOGGLE
    admin_mode = False
    if st.checkbox("🔐 Area Titolare"):
        pwd = st.text_input("Master Password", type="password")
        if pwd == ADMIN_PASS:
            admin_mode = True
            st.success("Accesso Admin Garantito")
        elif pwd:
            st.error("Password Errata")

# --- 8. ROUTING ---

# CASO A: ADMIN MODE ATTIVA
if admin_mode:
    render_admin_dashboard()
    st.stop() 

# CASO B: LOGIN SCREEN
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔑 Accedi", "📝 Registra Farmacista"])
    with tab1:
        with st.form("login"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Entra"):
                data = login_user(u, p)
                if data: 
                    st.session_state.logged_in = True; st.session_state.user_info = data; st.rerun()
                else: st.error("Errore login")
    with tab2:
        with st.form("reg"):
            nu = st.text_input("Nuovo User"); np = st.text_input("Nuova Pass", type="password")
            fn = st.text_input("Nome Completo"); ge = st.selectbox("Sesso", ["Uomo", "Donna"])
            if st.form_submit_button("Crea"):
                if save_user(nu, np, fn, ge): st.success("Creato! Vai su Accedi."); 
                else: st.error("User esiste già")
    st.stop()

# CASO C: PHARMACIST TRAINING MODE
sel_scenario = st.sidebar.selectbox("Training:", list(SCENARIOS.keys()))
hard = st.sidebar.toggle("🔥 Hard Mode")
if st.sidebar.button("Reset Chat"): st.session_state.messages = []; st.rerun()

curr = SCENARIOS[sel_scenario]
st.header(f"Simulazione: {sel_scenario}")
st.markdown(f"**Obiettivo:** {curr['obiettivo']}")

if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages: 
    with st.chat_message(m["role"]): st.write(m["content"])

# Tutor
if st.button("💡 Suggerimento"):
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    h = get_ai_response([{"role":"system","content":f"Tutor per: {curr['obiettivo']}. Suggerisci frase breve."},{"role":"user","content":hist}])
    st.info(f"Tip: {h}")

# --- INPUT AREA: VOCE O TESTO (MODIFICATO) ---
st.divider()
col_mic, col_text = st.columns([1, 8])

final_input = None

with col_mic:
    # Componente Microfono
    audio_data = mic_recorder(
        start_prompt="🎤",
        stop_prompt="⏹️",
        key='recorder',
        format="wav",
        use_container_width=True
    )

with col_text:
    text_input = st.chat_input("Scrivi qui la tua risposta...")

# LOGICA DI GESTIONE INPUT
if audio_data:
    with st.spinner("Trascrizione vocale..."):
        text_from_audio = transcribe_audio(audio_data['bytes'])
        if text_from_audio:
            final_input = text_from_audio
elif text_input:
    final_input = text_input

# --- ESECUZIONE CHAT ---
if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"): st.write(final_input)
    
    with st.spinner("..."):
        sys = curr['sys_prompt'] + (" Sii scontroso." if hard else "")
        ai_msg = get_ai_response([{"role":"system","content":sys}] + st.session_state.messages)
        asyncio.run(text_to_speech(ai_msg, curr['voice']))
    
    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
    with st.chat_message("assistant"): st.write(ai_msg); autoplay_audio("temp_audio.mp3")

# Evaluation
if len(st.session_state.messages)>2 and st.button("🏁 Valuta", type="primary", use_container_width=True):
    with st.spinner("Analisi..."):
        hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        prompt = f"Analisi {sel_scenario}. JSON: {{'score_empatia':1-10, 'score_tecnica':1-10, 'score_chiusura':1-10, 'score_ascolto':1-10, 'score_obiezioni':1-10, 'totale':0-100, 'revenue':euro, 'feedback_main':'txt', 'mistake':'txt', 'correction':'txt'}}\nCHAT:\n{hist}"
        res = get_ai_response([{"role":"user","content":prompt}], json_mode=True)
        try:
            d = json.loads(res)
            st.balloons()
            t1, t2 = st.tabs(["Performance", "Dettagli"])
            with t1: 
                c1,c2=st.columns(2)
                c1.plotly_chart(plot_radar([d['score_empatia'],d['score_tecnica'],d['score_chiusura'],d['score_ascolto'],d['score_obiezioni']]))
                c2.metric("Voto", f"{d['totale']}/100"); c2.metric("Fatturato", f"€ {d['revenue']}")
            with t2: st.error(d['mistake']); st.success(d['correction'])
            
            # Save KPI
            row = {"Date":datetime.now().strftime("%Y-%m-%d %H:%M"), "User": st.session_state.user_info['name'], "Scenario": sel_scenario, "Score": d['totale'], "Revenue": d['revenue']}
            try: pd.read_csv(KPI_FILE)._append(row, ignore_index=True).to_csv(KPI_FILE, index=False)
            except: pd.DataFrame([row]).to_csv(KPI_FILE, index=False)
        except: st.error("Errore report")