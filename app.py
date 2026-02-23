import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="MarketPulse | Intelligence IA", page_icon="📈", layout="wide")

# --- CSS CORRECTIF (Contraste Métriques & Flux) ---
st.markdown("""
    <style>
    /* Forçage du fond sombre pour toute la page */
    .stApp { background-color: #0E1117; }
    
    /* MÉTRIQUES : Fond sombre, texte blanc pur pour être lisible direct */
    div[data-testid="metric-container"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        padding: 20px !important;
        border-radius: 12px !important;
        color: white !important;
    }
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #CBD5E1 !important;
        font-size: 1rem !important;
    }

    /* FLUX GLOBAL : Forcer la visibilité des entêtes d'expanders */
    .stExpander summary p {
        color: #F8FAFC !important;
        font-weight: 600 !important;
        font-size: 1.05rem !important;
    }
    .stExpander {
        border: 1px solid #334155 !important;
        background-color: #0F172A !important;
        margin-bottom: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONNEXION FIRESTORE ---
@st.cache_resource
def init_db():
    try:
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict['project_id'])
    except:
        return firestore.Client.from_service_account_json("service-account.json")

db = init_db()

# --- CHARGEMENT ---
def load_data():
    if not db: return []
    # Tri sur 'date_extraction' car c'est ton index actif
    docs = db.collection('veilles_financieres').order_by(
        'date_extraction', direction=firestore.Query.DESCENDING
    ).limit(100).stream()
    return [doc.to_dict() for doc in docs]

raw_data = load_data()

if not raw_data:
    st.title("📉 MarketPulse")
    st.info("Base de données vide ou connexion en cours...")
else:
    df = pd.DataFrame(raw_data)
    df['dt'] = pd.to_datetime(df['date_extraction'])
    df['jour'] = df['dt'].dt.date

    # --- HEADER & MÉTRIQUES ---
    st.title("📉 MarketPulse")
    st.caption("Intelligence de marché | Moteur : Gemini 2.5 Flash")

    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Total Analyses", len(df))
    with m2: st.metric("Analystes Actifs", len(df['source'].unique()))
    with m3:
        all_t = df.explode('tickers')['tickers'].dropna().str.replace('$', '', regex=False)
        top_ticker = f"${all_t.mode()[0]}" if not all_t.empty else "Macro"
        st.metric("Focus Majoritaire", top_ticker)
    with m4: st.metric("Dernier Scan", df['dt'].iloc[0].strftime("%H:%M:%S"))

    st.markdown("---")

    # --- SECTION VISUALISATIONS (LES BLOCS PERTINENTS REPRIS) ---
    col_graph, col_pie = st.columns([2, 1])

    with col_graph:
        st.subheader("🔥 Concentration des Tickers")
        df_t = df.explode('tickers').dropna()
        if not df_t.empty:
            counts = df_t['tickers'].value_counts().reset_index()
            counts.columns = ['Ticker', 'Mentions']
            fig_bar = px.bar(counts.head(15), x='Mentions', y='Ticker', orientation='h',
                             color='Mentions', color_continuous_scale='Blues', template="plotly_dark")
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.subheader("🗣️ Part de Voix")
        src_counts = df['source'].value_counts().reset_index()
        src_counts.columns = ['Auteur', 'Nombre']
        fig_pie = px.pie(src_counts, values='Nombre', names='Auteur', hole=0.4, template="plotly_dark")
        fig_pie.update_layout(margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    # Graphique temporel pour voir l'intensité
    st.subheader("📅 Volume d'Activité")
    daily_vol = df.groupby('jour').size().reset_index(name='Volume')
    fig_line = px.line(daily_vol, x='jour', y='Volume', markers=True, template="plotly_dark")
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")

    # --- RECHERCHE ET FLUX ---
    tab_flow, tab_search = st.tabs(["📑 Flux Global", "🔍 Recherche par Ticker"])

    with tab_flow:
        st.sidebar.header("Filtres")
        sources_list = sorted(df['source'].unique())
        selected = st.sidebar.multiselect("Filtrer par Analyste", sources_list, default=sources_list)
        
        df_display = df[df['source'].isin(selected)]
        for _, row in df_display.iterrows():
            # Forçage de la couleur de l'entête via CSS plus haut
            with st.expander(f"@{row['source']} | {row['dt'].strftime('%d/%m %H:%M')}"):
                if row.get('tickers'):
                    st.markdown(f"**Focus :** `{'`, `'.join(row['tickers'])}`")
                st.write(row['texte'])
                st.caption(f"ID : {row['id']}")

    with tab_search:
        query = st.text_input("Symbole (ex: MU, PANW, NVDA)").upper().strip().replace('$', '')
        if query:
            # Recherche robuste qui ignore le '$' de la base
            def match_ticker(t_list, target):
                if not isinstance(t_list, list): return False
                return any(target == t.replace('$', '').upper() for t in t_list)

            results = df[df['tickers'].apply(lambda x: match_ticker(x, query))]
            
            if not results.empty:
                st.success(f"{len(results)} analyse(s) trouvée(s) pour ${query}")
                for _, row in results.iterrows():
                    st.write(f"**{row['source']}** ({row['dt'].strftime('%d/%m')})")
                    st.write(row['texte'])
                    st.divider()
            else:
                st.warning(f"Aucune thèse sur ${query} n'a été trouvée récemment.")