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
from streamlit_mic_recorder import mic_recorder
import io
import random

# --- 1. CONFIGURAZIONE & STILE (invariato) ---
st.set_page_config(page_title="PharmaFlow AI Suite", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
    .stApp {background-color: #f4f6f9;}
    div[data-testid="stSidebar"] {background-color: #2c3e50; color: white;}
    .stMetric {background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    h1, h2, h3 {color: #2c3e50;}
    .dataframe {font-size: 14px !important;}
    button[kind="secondary"] {border-radius: 50px; border: 1px solid #ddd; height: 3rem;}
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTH SYSTEM (invariato) ---
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

# --- 3. MOTORE AI (GROQ) (invariato) ---
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
            max_tokens=2048,  # Aumentato per report più dettagliati
            response_format={"type": "json_object"} if json_mode else None
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Errore AI: {e}"

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
        return None

# --- 4. DATA & SCENARIOS (POTENZIATI) ---
# Aggiunti campi: personalita, contesto, obiezioni_tipiche, stile_comunicazione
SCENARIOS = {
    "Dolore Articolare (Anziano)": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Maria, 70 anni, pensionata, vive da sola.",
        "personalita": "diffidente verso i farmaci nuovi, si fida solo del Voltaren, ma è anche ansiosa per la salute.",
        "contesto": "cliente abituale, conosce la farmacia, ha budget limitato (pensione).",
        "obiezioni_tipiche": ["costo troppo alto", "non mi fido delle novità", "mia figlia dice che il collagene fa ingrassare"],
        "obiettivo": "Vendere: Crema FANS + Collagene.",
        "sys_prompt": "Sei Maria. Hai male al ginocchio. Vuoi solo il Voltaren. Sei diffidente, ma se il farmacista è empatico e spiega bene il beneficio a lungo termine del collagene, potresti cedere. Reagisci alle obiezioni in modo naturale, tenendo conto della tua personalità.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai dimenticato il bancomat a casa, hai solo 15 euro in contanti.",
            "IMPREVISTO: Sei allergica all'Aspirina/FANS (ma non lo sai con certezza, chiedi).",
            "IMPREVISTO: Tua figlia ti ha detto che il collagene fa ingrassare."
        ]
    },
    "Cervicale e Stress": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Marco, 45 anni, impiegato, stressato.",
        "personalita": "frettoloso, vuole soluzioni veloci, scettico sugli integratori.",
        "contesto": "cliente nuovo, entra di fretta, probabilmente durante pausa pranzo.",
        "obiezioni_tipiche": ["voglio solo una pastiglia forte", "gli integratori non servono a niente", "ho poca pazienza"],
        "obiettivo": "Vendere: Cerotti + Magnesio.",
        "sys_prompt": "Sei Marco. Collo bloccato. Vuoi una pastiglia forte. Rifiuti il magnesio perché pensi sia inutile. Se il farmacista ti spiega che il magnesio scioglie la contrattura muscolare e lo fa in modo rapido, potresti accettare. Se insisti troppo, ti innervosisci.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Hai la pelle molto sensibile, i cerotti ti fanno allergia.",
            "IMPREVISTO: Sei diabetico. Chiedi se il Magnesio contiene zucchero.",
            "IMPREVISTO: Il telefono squilla durante la conversazione (devi interrompere)."
        ]
    },
    "Mal di Testa (Donna)": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Chiara, 30 anni, insegnante.",
        "personalita": "razionale, informata, ma influenzabile da quello che legge online.",
        "contesto": "cliente che cerca un farmaco per il mal di testa ricorrente, forse legato allo stress.",
        "obiezioni_tipiche": ["ho letto che l'ibuprofene non fa bene", "voglio qualcosa di naturale", "mi preoccupano gli effetti collaterali"],
        "obiettivo": "Vendere: Ibuprofene + Coadiuvante (magnesio o relax).",
        "sys_prompt": "Sei Chiara. Cerchio alla testa. Di solito prendi il Moment. Sei aperta a integratori se ti spiegano che aiutano la stanchezza mentale. Se il farmacista usa termini troppo tecnici, ti insospettisci.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sospetti di essere incinta (niente FANS).",
            "IMPREVISTO: La caffeina ti fa venire la tachicardia."
        ]
    },
    "Tosse Secca (Fumatore)": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Roberto, 50 anni, fumatore, operaio.",
        "personalita": "un po' ruvido, ma preoccupato per la salute, anche se non lo dà a vedere.",
        "contesto": "cliente che viene spesso per problemi respiratori, fuma molto.",
        "obiezioni_tipiche": ["sciroppo? ma è pieno di zucchero", "lo spray mi sembra una cosa da bambini", "tanto smetterò di fumare... un giorno"],
        "obiettivo": "Vendere: Sciroppo + Spray (o dispositivo per proteggere le vie aeree).",
        "sys_prompt": "Sei Roberto. Tosse secca da fumo. Rifiuti lo spray perché pensi sia poco efficace. Accetti solo se spieghi che lo spray protegge il catrame. Se il farmacista ti fa una predica sul fumo, ti chiudi.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Sei diabetico, niente zuccheri.",
            "IMPREVISTO: Dì che tua moglie ti stressa per smettere di fumare."
        ]
    },
    "Influenza (Prevenzione)": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Giovanna, 75 anni, pensionata, ipertesa.",
        "personalita": "attenta alla salute, segue i consigli del medico, ma ha paura delle influenze.",
        "contesto": "cliente abituale, spesso chiede consigli preventivi.",
        "obiezioni_tipiche": ["le pastiglie grosse non le inghiotto", "prendo già tante medicine", "la vitamina C serve a qualcosa?"],
        "obiettivo": "Vendere: Tachipirina + Vitamina C o integratore per difese immunitarie.",
        "sys_prompt": "Sei Giovanna. Paura dell'influenza. Vuoi comprare la Tachipirina. Accetti la prevenzione solo se spieghi che serve per le difese basse. Se proponi qualcosa che interagisce con i suoi farmaci (Coumadin), devi avvertirla.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Non riesci a deglutire le pastiglie grosse.",
            "IMPREVISTO: Prendi il Coumadin (anticoagulante)."
        ]
    },
    "Reflusso Gastrico": {
        "voice": "it-IT-DiegoNeural",
        "persona": "Giuseppe, 55 anni, imprenditore, vive di corsa.",
        "personalita": "fumatore, beve caffè, non ha tempo per curarsi.",
        "contesto": "cliente che cerca una soluzione rapida al bruciore.",
        "obiezioni_tipiche": ["i probiotici mi gonfiano", "voglio qualcosa che agisca subito", "ho la pressione alta, posso?"],
        "obiettivo": "Vendere: Antiacido + Probiotici (o fermenti).",
        "sys_prompt": "Sei Giuseppe. Bruciore. Compri probiotici SOLO se spiegano che riparano la mucosa. Se hai fretta, potresti prendere solo l'antiacido e andartene.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Soffri di pressione alta (no sodio).",
            "IMPREVISTO: Dì che i fermenti lattici ti gonfiano la pancia."
        ]
    },
    "Gonfiore Addominale": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Simona, 35 anni, impiegata, attenta alla linea.",
        "personalita": "un po' ansiosa per i problemi intestinali, ha provato già vari rimedi.",
        "contesto": "cliente che ha una cena importante stasera e cerca una soluzione veloce.",
        "obiezioni_tipiche": ["voglio effetto immediato", "gli enzimi cosa sono?", "ho paura di effetti collaterali"],
        "obiettivo": "Vendere: Carbone + Enzimi.",
        "sys_prompt": "Sei Simona. Gonfia. Rifiuti gli enzimi perché non li conosci. Accetti SOLO se spiegano differenza col carbone. Se hai fretta, potresti prendere solo il carbone.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Ti serve effetto immediato per una cena stasera.",
            "IMPREVISTO: Sei in ritardo e devi andare via."
        ]
    },
    "Terapia Antibiotica": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Laura, 40 anni, mamma di due bambini.",
        "personalita": "preoccupata per i figli, cerca di seguire le prescrizioni ma ha dubbi.",
        "contesto": "ha la ricetta per l'antibiotico per il figlio piccolo.",
        "obiezioni_tipiche": ["i fermenti servono davvero?", "come si prendono?", "a stomaco pieno o vuoto?"],
        "obiettivo": "Vendere: Antibiotico + Fermenti.",
        "sys_prompt": "Sei Laura. Ricetta antibiotico per il bambino. Rifiuti i fermenti perché pensi siano inutili. Accetti SOLO se spieghi il rischio di diarrea. Se il farmacista è gentile e spiega bene, diventi più fiduciosa.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Il bambino vomita le fialette.",
            "IMPREVISTO: Chiedi se va preso a stomaco pieno o vuoto."
        ]
    },
    "Insonnia e Stress": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Giulia, 42 anni, libera professionista.",
        "personalita": "stressata, dorme male, è scettica sui rimedi naturali perché li ha già provati senza successo.",
        "contesto": "cliente che cerca una soluzione per l'insonnia, forse anche ansia.",
        "obiezioni_tipiche": ["la melatonina non mi fa niente", "voglio qualcosa di forte", "ho paura di dipendenza"],
        "obiettivo": "Vendere: Melatonina + Magnesio (o prodotti specifici).",
        "sys_prompt": "Sei Giulia. Dormi male. Sei scettica sui naturali. Se il farmacista ti spiega che esistono formulazioni a rilascio prolungato (per chi si sveglia alle 3) potresti convincerti.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Ti svegli sempre alle 3 di notte (serve Retard).",
            "IMPREVISTO: Hai già provato la melatonina senza risultati."
        ]
    },
    "Anti-Age Viso": {
        "voice": "it-IT-ElsaNeural",
        "persona": "Elena, 55 anni, insegnante di yoga.",
        "personalita": "attenta all'estetica, informata, ma ha la pelle mista e cerca prodotti non untuosi.",
        "contesto": "cliente che cerca una crema anti-età, magari ha già provato diversi prodotti.",
        "obiezioni_tipiche": ["la crema unge troppo", "il siero è necessario?", "ho la pelle sensibile"],
        "obiettivo": "Vendere: Crema + Siero.",
        "sys_prompt": "Sei Elena. Vuoi crema. Rifiuti il siero perché pensi sia un extra. Accetti solo se spiegano che il siero veicola i principi attivi in profondità. Se il farmacista capisce che hai pelle mista e propone prodotti adatti, apprezzi.",
        "twists": [
            "Nessun imprevisto.",
            "IMPREVISTO: Pelle mista che si lucida.",
            "IMPREVISTO: Sei di fretta, vuoi solo una crema veloce."
        ]
    }
}

# --- 5. FUNZIONI UTILI (invariate) ---
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
    categories = ['Empatia', 'Tecnica', 'Chiusura', 'Ascolto', 'Gestione Obiezioni']
    fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself', name='Tu'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), showlegend=False, margin=dict(t=20, b=20, l=40, r=40))
    return fig

# --- 6. DASHBOARD TITOLARE (ADMIN) - POTENZIATA CON NUOVI KPI ---
def render_admin_dashboard():
    st.title("📊 PharmaBoss Dashboard")
    if not os.path.exists(KPI_FILE):
        st.warning("Nessun dato registrato. Fai fare la prima simulazione ai tuoi dipendenti!")
        return

    df = pd.read_csv(KPI_FILE)
    
    # Aggiungiamo metriche basate sui nuovi campi (se presenti)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fatturato Potenziale", f"€ {df['Revenue'].sum()}")
    col2.metric("Media Voto Team", f"{int(df['Score'].mean())}/100")
    col3.metric("Simulazioni Totali", len(df))
    col4.metric("Farmacisti Attivi", df['User'].nunique())
    
    st.divider()
    
    # Se sono disponibili i nuovi dati (es. lost_revenue), possiamo mostrarli
    if 'LostRevenue' in df.columns:
        st.subheader("💰 Impatto Economico degli Errori")
        totale_lost = df['LostRevenue'].sum()
        st.metric("Totale Lost Revenue (simulazioni)", f"€ {totale_lost:.2f}")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("🏆 Top Performer")
        leaderboard = df.groupby('User').agg({'Score': 'mean', 'Revenue': 'sum', 'Scenario': 'count'}).reset_index()
        leaderboard = leaderboard.sort_values(by='Revenue', ascending=False)
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
    with c2:
        st.subheader("📉 Aree Critiche")
        weakness = df.groupby('Scenario')['Score'].mean().sort_values()
        fig_bar = px.bar(weakness, x='Score', y=weakness.index, orientation='h', color='Score', title="Media Voto per Caso")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()
    st.subheader("🔎 Analisi Singolo Dipendente")
    selected_emp = st.selectbox("Seleziona Farmacista:", df['User'].unique())
    emp_df = df[df['User'] == selected_emp]
    fig_line = px.line(emp_df, x=emp_df.index, y='Score', markers=True, title=f"Trend Miglioramento: {selected_emp}")
    st.plotly_chart(fig_line, use_container_width=True)
    st.write("🛑 **Ultimi Errori Rilevati:**")
    # Se abbiamo il campo 'Mistake' possiamo mostrarlo
    if 'Mistake' in emp_df.columns:
        st.table(emp_df[['Scenario', 'Score', 'Mistake']].tail(5))
    else:
        st.table(emp_df[['Scenario', 'Score']].tail(5))

# --- 7. SIDEBAR LOGIC (invariata, ma aggiungiamo nuove opzioni) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}
    st.session_state.training_mode = "standard"  # per future modalità (maieuta, ecc.)
    st.session_state.user_history = []  # per tracciare errori ricorrenti (semplice)

with st.sidebar:
    st.title("PharmaFlow 🎲")
    
    if st.session_state.logged_in:
        user = st.session_state.user_info
        st.write(f"**{user['avatar']} {user['name']}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.divider()
    
    # Nuove opzioni di training
    if st.session_state.logged_in:
        st.subheader("Modalità di allenamento")
        training_mode = st.radio(
            "Focus:",
            ["Standard", "Maieuta (domande aperte)", "Obiezioni", "Cross-selling"],
            index=0
        )
        st.session_state.training_mode = training_mode.lower()
        
        st.divider()
    
    admin_mode = False
    if st.checkbox("🔐 Area Titolare"):
        pwd = st.text_input("Master Password", type="password")
        if pwd == ADMIN_PASS:
            admin_mode = True
            st.success("Accesso Admin Garantito")
        elif pwd:
            st.error("Password Errata")

# --- 8. ROUTING ---

if admin_mode:
    render_admin_dashboard()
    st.stop()

# CASO B: LOGIN SCREEN (invariato)
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔑 Accedi", "📝 Registra Farmacista"])
    with tab1:
        with st.form("login"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Entra"):
                data = login_user(u, p)
                if data: 
                    st.session_state.logged_in = True
                    st.session_state.user_info = data
                    st.rerun()
                else: 
                    st.error("Errore login")
    with tab2:
        with st.form("reg"):
            nu = st.text_input("Nuovo User"); np = st.text_input("Nuova Pass", type="password")
            fn = st.text_input("Nome Completo"); ge = st.selectbox("Sesso", ["Uomo", "Donna"])
            if st.form_submit_button("Crea"):
                if save_user(nu, np, fn, ge): 
                    st.success("Creato! Vai su Accedi.")
                else: 
                    st.error("Esiste già")
    st.stop()

# CASO C: PHARMACIST TRAINING MODE (POTENZIATO)
sel_scenario = st.sidebar.selectbox("Training:", list(SCENARIOS.keys()))
hard = st.sidebar.toggle("🔥 Hard Mode (cliente scontroso)")

# --- GESTIONE ROGUE MODE (Imprevisti) ---
if "current_scenario" not in st.session_state: st.session_state.current_scenario = ""
if "current_twist" not in st.session_state: st.session_state.current_twist = ""

trigger_reset = st.sidebar.button("🎲 Nuova Simulazione")

if trigger_reset or st.session_state.current_scenario != sel_scenario:
    st.session_state.messages = []
    st.session_state.current_scenario = sel_scenario
    # Pesca un imprevisto casuale
    possible_twists = SCENARIOS[sel_scenario].get('twists', ["Nessun imprevisto."])
    st.session_state.current_twist = random.choice(possible_twists)
    # Resetta anche eventuali dati di sessione per il training adattivo (semplice)
    st.session_state.conversation_ended = False
    st.rerun()

curr = SCENARIOS[sel_scenario]
st.header(f"Simulazione: {sel_scenario}")
# Mostriamo ora anche personalità e contesto per dare più consapevolezza
with st.expander("👤 Profilo del paziente", expanded=False):
    st.markdown(f"**Persona:** {curr['persona']}")
    st.markdown(f"**Personalità:** {curr.get('personalita', 'Non specificata')}")
    st.markdown(f"**Contesto:** {curr.get('contesto', 'Non specificato')}")
    st.markdown(f"**Obiettivo vendita:** {curr['obiettivo']}")
    if st.session_state.current_twist != "Nessun imprevisto.":
        st.warning(f"⚠️ Imprevisto attivo: {st.session_state.current_twist}")

# --- GESTIONE CONVERSAZIONE ---
if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages: 
    with st.chat_message(m["role"]): st.write(m["content"])

# Bottone suggerimento (invariato)
if st.button("💡 Suggerimento"):
    hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    # Suggerimento più contestuale, basato sulla personalità
    prompt_suggerimento = f"Sei un coach di vendita per farmacisti. Il paziente ha questa personalità: {curr.get('personalita', '')}. Obiettivo: {curr['obiettivo']}. Basandoti sulla conversazione finora, dai un suggerimento breve e pratico su cosa dire o chiedere dopo."
    h = get_ai_response([{"role":"system","content":prompt_suggerimento},{"role":"user","content":hist}])
    st.info(f"💡 Suggerimento: {h}")

st.divider()
col_mic, col_text = st.columns([1, 8])
final_input = None

with col_mic:
    audio_data = mic_recorder(start_prompt="🎤", stop_prompt="⏹️", key='recorder', format="wav", use_container_width=True)

with col_text:
    text_input = st.chat_input("Scrivi qui la tua risposta...")

if audio_data:
    with st.spinner("Trascrizione vocale..."):
        text_from_audio = transcribe_audio(audio_data['bytes'])
        if text_from_audio: final_input = text_from_audio
elif text_input:
    final_input = text_input

if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"): st.write(final_input)
    
    with st.spinner("..."):
        # Costruzione prompt system per il paziente con tutte le informazioni
        personalita = curr.get('personalita', '')
        contesto = curr.get('contesto', '')
        obiezioni = curr.get('obiezioni_tipiche', [])
        twist = st.session_state.current_twist
        
        sys_prompt_base = curr['sys_prompt']
        sys_prompt = f"{sys_prompt_base}\n\nPersonalità: {personalita}\nContesto: {contesto}\nObiezioni tipiche che potresti sollevare: {', '.join(obiezioni)}"
        if twist != "Nessun imprevisto.":
            sys_prompt += f"\n\nIMPORTANTE: In questa sessione c'è un imprevisto: {twist}. Reagisci di conseguenza."
        if hard:
            sys_prompt += " Inoltre, sii scontroso e poco collaborativo."
        
        # Se la modalità è "maieuta", il paziente potrebbe essere più taciturno per stimolare domande? (opzionale)
        if st.session_state.training_mode == "maieuta (domande aperte)":
            sys_prompt += " In questa sessione, rispondi in modo breve se ti vengono fatte domande chiuse, ma se il farmacista ti fa domande aperte, fornisci più dettagli."
        
        ai_msg = get_ai_response([{"role":"system","content":sys_prompt}] + st.session_state.messages)
        asyncio.run(text_to_speech(ai_msg, curr['voice']))
    
    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
    with st.chat_message("assistant"): st.write(ai_msg); autoplay_audio("temp_audio.mp3")

# --- VALUTAZIONE AVANZATA (con report ricco) ---
if len(st.session_state.messages) > 2 and not st.session_state.get("conversation_ended", False):
    if st.button("🏁 Valuta e concludi", type="primary", use_container_width=True):
        with st.spinner("Analisi approfondita in corso..."):
            hist = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            # Prompt per ottenere un JSON ricco di dettagli
            prompt_valutazione = f"""Sei un supervisore esperto di tecniche di vendita in farmacia. Analizza la conversazione seguente tra un farmacista (user) e un paziente (assistant). 
Scenario: {sel_scenario}
Imprevisto: {st.session_state.current_twist}
Personalità del paziente: {curr.get('personalita', '')}
Contesto: {curr.get('contesto', '')}

Fornisci una valutazione dettagliata in formato JSON con i seguenti campi:
- score_empatia (1-10): capacità di mettersi nei panni del paziente
- score_tecnica (1-10): conoscenza dei prodotti e appropriatezza della proposta
- score_chiusura (1-10): capacità di concludere la vendita e proporre cross-selling
- score_ascolto (1-10): capacità di fare domande aperte e ascoltare i bisogni
- score_obiezioni (1-10): gestione delle obiezioni
- totale (0-100): voto complessivo
- revenue (numero): fatturato generato (stima in euro)
- lost_revenue (numero): stima di quanto avrebbe potuto guadagnare in più (es. cross-selling mancato)
- analisi_bias (stringa): spiega se il farmacista ha usato correttamente leve psicologiche (autorità, riprova sociale, ecc.) o quali ha mancato
- parole_killer (lista di stringhe): frasi deboli o negative dette dal farmacista
- parole_magiche (lista di stringhe): esempi di frasi potenti che avrebbe potuto usare
- matrice_tecniche (oggetto con booleani): 
    {{
        "accoglienza": true/false,
        "analisi_bisogno": true/false,
        "proposta_valore": true/false,
        "gestione_obiezione": true/false,
        "chiusura": true/false,
        "cross_selling": true/false
    }}
- rewind_fix (oggetto): {{"frase_sbagliata": "...", "frase_corretta": "..."}}  (la frase peggiore e come avrebbe dovuto dirla)
- analisi_obiezioni (lista di oggetti): per ogni obiezione sollevata dal paziente, riporta:
    {{"obiezione": "...", "risposta_farmacista": "...", "feedback": "..."}}
- suggerimenti_gergo (stringa): consigli su termini tecnici o linguaggio adatto al contesto italiano
- feedback_generale (stringa): un paragrafo di consigli complessivi
- mistake (stringa): breve descrizione dell'errore principale (per compatibilità con vecchio report)
- correction (stringa): come correggere l'errore principale
- impatto_annuale (stringa): calcola (basato su lost_revenue) una stima dell'impatto annuale se l'errore si ripete (es. "Con 10 clienti a settimana, perdi 5000€ l'anno")

Conversazione:
{hist}

Rispondi SOLO con un JSON valido.
"""
            res = get_ai_response([{"role":"user","content":prompt_valutazione}], json_mode=True)
            try:
                d = json.loads(res)
                st.balloons()
                
                # Tabs per il report avanzato
                tab_perf, tab_dettagli, tab_tecniche, tab_economia, tab_coach = st.tabs(
                    ["📊 Performance", "🔍 Dettagli errori", "📋 Tecniche", "💰 Impatto economico", "🎓 Coach"]
                )
                
                with tab_perf:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.plotly_chart(plot_radar([
                            d.get('score_empatia', 0),
                            d.get('score_tecnica', 0),
                            d.get('score_chiusura', 0),
                            d.get('score_ascolto', 0),
                            d.get('score_obiezioni', 0)
                        ]), use_container_width=True)
                    with col2:
                        st.metric("Voto complessivo", f"{d.get('totale', 0)}/100")
                        st.metric("Fatturato generato", f"€ {d.get('revenue', 0)}")
                        if d.get('lost_revenue', 0) > 0:
                            st.metric("Opportunità perse", f"€ {d['lost_revenue']}", delta_color="inverse")
                    
                    if st.session_state.current_twist != "Nessun imprevisto.":
                        st.info(f"⚠️ Imprevisto affrontato: {st.session_state.current_twist}")
                    
                    # Analisi bias
                    if d.get('analisi_bias'):
                        st.subheader("🧠 Analisi dei bias cognitivi")
                        st.write(d['analisi_bias'])
                
                with tab_dettagli:
                    if d.get('parole_killer'):
                        st.error("❌ Parole killer (da evitare)")
                        for frase in d['parole_killer']:
                            st.markdown(f"- {frase}")
                    if d.get('parole_magiche'):
                        st.success("✨ Parole magiche (da usare)")
                        for frase in d['parole_magiche']:
                            st.markdown(f"- {frase}")
                    
                    st.divider()
                    
                    if d.get('rewind_fix'):
                        st.subheader("⏪ Rewind & Fix")
                        st.markdown(f"**Hai detto:** {d['rewind_fix'].get('frase_sbagliata', '')}")
                        st.markdown(f"**Avresti dovuto dire:** {d['rewind_fix'].get('frase_corretta', '')}")
                    
                    st.divider()
                    
                    # Errori principali (compatibilità)
                    if d.get('mistake'):
                        st.error(f"**Errore principale:** {d['mistake']}")
                    if d.get('correction'):
                        st.success(f"**Correzione:** {d['correction']}")
                
                with tab_tecniche:
                    st.subheader("📋 Matrice delle tecniche di vendita")
                    tecniche = d.get('matrice_tecniche', {})
                    cols = st.columns(3)
                    with cols[0]:
                        st.write("✅ **Accoglienza**" if tecniche.get('accoglienza') else "❌ Accoglienza")
                        st.write("✅ **Analisi bisogno**" if tecniche.get('analisi_bisogno') else "❌ Analisi bisogno")
                    with cols[1]:
                        st.write("✅ **Proposta valore**" if tecniche.get('proposta_valore') else "❌ Proposta valore")
                        st.write("✅ **Gestione obiezione**" if tecniche.get('gestione_obiezione') else "❌ Gestione obiezione")
                    with cols[2]:
                        st.write("✅ **Chiusura**" if tecniche.get('chiusura') else "❌ Chiusura")
                        st.write("✅ **Cross-selling**" if tecniche.get('cross_selling') else "❌ Cross-selling")
                    
                    st.divider()
                    
                    if d.get('analisi_obiezioni'):
                        st.subheader("🗣️ Analisi obiezioni")
                        for ob in d['analisi_obiezioni']:
                            with st.expander(f"Obiezione: {ob.get('obiezione', '')}"):
                                st.markdown(f"**Risposta data:** {ob.get('risposta_farmacista', '')}")
                                st.markdown(f"**Feedback:** {ob.get('feedback', '')}")
                
                with tab_economia:
                    st.subheader("💰 Impatto economico degli errori")
                    lost = d.get('lost_revenue', 0)
                    if lost > 0:
                        st.metric("Lost revenue in questa simulazione", f"€ {lost}")
                    if d.get('impatto_annuale'):
                        st.warning(d['impatto_annuale'])
                    else:
                        # Calcolo semplice se non fornito
                        if lost > 0:
                            st.info(f"Se questo errore capita con 10 clienti a settimana, in un anno perdi circa € {lost * 10 * 52:.0f}")
                
                with tab_coach:
                    st.subheader("🎓 Consigli del coach")
                    if d.get('feedback_generale'):
                        st.write(d['feedback_generale'])
                    if d.get('suggerimenti_gergo'):
                        st.info(f"💬 **Suggerimenti sul linguaggio:** {d['suggerimenti_gergo']}")
                    
                    # Training adattivo: registriamo l'errore per future raccomandazioni
                    if d.get('mistake'):
                        # Semplice tracciamento in sessione
                        if "user_history" not in st.session_state:
                            st.session_state.user_history = []
                        st.session_state.user_history.append({
                            "scenario": sel_scenario,
                            "errore": d['mistake'],
                            "categoria": "cross_selling" if "cross" in d['mistake'].lower() else "obiezioni" if "obiezione" in d['mistake'].lower() else "altro"
                        })
                        # Suggerimento per il prossimo allenamento
                        st.divider()
                        st.markdown("**📈 Prossimo allenamento consigliato:**")
                        # Analisi semplice degli errori ricorrenti
                        from collections import Counter
                        if len(st.session_state.user_history) >= 3:
                            errori_cat = [e['categoria'] for e in st.session_state.user_history[-3:]]
                            comune = Counter(errori_cat).most_common(1)[0][0]
                            if comune == "cross_selling":
                                st.info("🎯 Sembra che tu abbia difficoltà con il cross-selling. Nella prossima simulazione, concentrati su come proporre un prodotto aggiuntivo in modo naturale.")
                            elif comune == "obiezioni":
                                st.info("🎯 Hai faticato a gestire le obiezioni. Prova la modalità 'Obiezioni' per esercitarti.")
                            else:
                                st.info("Continua ad allenarti!")
                
                # Salvataggio dei dati (espandiamo il CSV con nuovi campi)
                row = {
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "User": st.session_state.user_info['name'],
                    "Scenario": sel_scenario,
                    "Score": d.get('totale', 0),
                    "Revenue": d.get('revenue', 0),
                    "LostRevenue": d.get('lost_revenue', 0),
                    "Mistake": d.get('mistake', ''),
                    "Correction": d.get('correction', ''),
                    "Empatia": d.get('score_empatia', 0),
                    "Tecnica": d.get('score_tecnica', 0),
                    "Chiusura": d.get('score_chiusura', 0),
                    "Ascolto": d.get('score_ascolto', 0),
                    "Obiezioni": d.get('score_obiezioni', 0)
                }
                try:
                    df = pd.read_csv(KPI_FILE)
                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                    df.to_csv(KPI_FILE, index=False)
                except:
                    pd.DataFrame([row]).to_csv(KPI_FILE, index=False)
                
                st.session_state.conversation_ended = True
                
            except json.JSONDecodeError:
                st.error("Errore nel parsing della risposta AI. Riprova.")
                st.text(res)  # Mostra la risposta grezza per debug