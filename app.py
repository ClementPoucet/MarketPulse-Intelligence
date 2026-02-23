import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="MarketPulse | Intelligence Marché",
    page_icon="📈",
    layout="wide"
)

# --- STYLE CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONNEXION FIRESTORE ---
@st.cache_resource
def init_db():
    try:
        # Utilisation du secret 'textkey' configuré sur Streamlit Cloud
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict['project_id'])
    except Exception as e:
        st.error(f"Erreur de configuration des secrets : {e}")
        return None

db = init_db()

# --- CHARGEMENT DES DONNÉES ---
def load_data():
    if db is None: return []
    # On récupère les 100 dernières entrées
    docs = db.collection('veilles_financieres').order_by(
        'date', direction=firestore.Query.DESCENDING
    ).limit(100).stream()
    return [doc.to_dict() for doc in docs]

raw_data = load_data()

# --- CORPS PRINCIPAL ---
if not raw_data:
    st.title("📈 FinSight Alpha")
    st.info("En attente de données en provenance de Firestore. Lancez votre pipeline d'ingestion.")
else:
    df = pd.DataFrame(raw_data)
    # Conversion de la colonne date en objets datetime pour les graphiques
    df['date_dt'] = pd.to_datetime(df['date'])
    df['jour'] = df['date_dt'].dt.date

    # --- SIDEBAR (FILTRES) ---
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2585/2585092.png", width=100)
    st.sidebar.title("Configuration")
    
    sources = sorted(df['source'].unique())
    selected_sources = st.sidebar.multiselect("Filtrer par Analyste", sources, default=sources)
    
    df_filtered = df[df['source'].isin(selected_sources)]

    # --- TITRE ET MÉTRIQUES ---
    st.title("📈 FinSight Alpha Dashboard")
    st.subheader("Analyse quantitative des thèses de marché")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Analyses", len(df))
    with m2:
        st.metric("Analystes Actifs", len(df['source'].unique()))
    with m3:
        top_ticker = df.explode('tickers')['tickers'].mode()[0] if not df.explode('tickers').empty else "N/A"
        st.metric("Ticker le plus cité", top_ticker)
    with m4:
        st.metric("Dernière mise à jour", df['date_dt'].iloc[0].strftime("%H:%M:%S"))

    st.markdown("---")

    # --- SECTION VISUALISATIONS ---
    col_left, col_right = st.columns(2)

    with col_left:
        # 1. Histogramme des Tickers les plus cités
        st.markdown("#### 🔥 Concentration des Actifs")
        df_tickers = df_filtered.explode('tickers')
        if not df_tickers['tickers'].dropna().empty:
            ticker_counts = df_tickers['tickers'].value_counts().reset_index()
            ticker_counts.columns = ['Ticker', 'Mentions']
            fig_tickers = px.bar(
                ticker_counts.head(12), 
                x='Mentions', y='Ticker', 
                orientation='h',
                color='Mentions',
                color_continuous_scale='Blues',
                template="plotly_dark"
            )
            fig_tickers.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_tickers, use_container_width=True)
        else:
            st.write("Aucun ticker détecté sur la période.")

    with col_right:
        # 2. Répartition de l'activité par Source
        st.markdown("#### 🗣️ Part de Voix par Analyste")
        source_counts = df_filtered['source'].value_counts().reset_index()
        source_counts.columns = ['Auteur', 'Nombre']
        fig_pie = px.pie(
            source_counts, 
            values='Nombre', names='Auteur',
            hole=0.4,
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    # 3. Graphique Temporel (Volume d'extractions)
    st.markdown("#### 📅 Intensité de l'Activité")
    daily_activity = df_filtered.groupby('jour').size().reset_index(name='Volume')
    fig_time = px.line(
        daily_activity, 
        x='jour', y='Volume',
        title="Volume d'analyses quotidiennes",
        template="plotly_dark",
        markers=True
    )
    fig_time.update_traces(line_color='#00d1b2')
    st.plotly_chart(fig_time, use_container_width=True)

    st.markdown("---")

    # --- SECTION FLUX DE DONNÉES ---
    st.markdown("### 📝 Flux des Thèses d'Investissement")
    
    # On utilise des tabs pour organiser par auteur ou voir tout le flux
    tab_all, tab_search = st.tabs(["Tout le flux", "Recherche par Ticker"])

    with tab_all:
        for index, row in df_filtered.iterrows():
            with st.expander(f"@{row['source']} | {row['date_dt'].strftime('%d/%m/%Y %H:%M')}"):
                col_t1, col_t2 = st.columns([1, 4])
                with col_t1:
                    if row['tickers']:
                        for t in row['tickers']:
                            st.info(f"**{t}**")
                    else:
                        st.write("Aucun ticker")
                with col_t2:
                    st.write(row['texte'])
                    st.caption(f"ID : {row['id']}")

    with tab_search:
        search_ticker = st.text_input("Entrez un ticker (ex: NVDA)").upper().replace('$', '')
        if search_ticker:
            mask = df_filtered['tickers'].apply(lambda x: search_ticker in x if isinstance(x, list) else False)
            results = df_filtered[mask]
            if not results.empty:
                for _, row in results.iterrows():
                    st.write(f"**{row['source']}** ({row['date_dt'].strftime('%d/%m')})")
                    st.write(row['texte'])
                    st.markdown("---")
            else:
                st.write("Aucune mention trouvée pour ce ticker.")