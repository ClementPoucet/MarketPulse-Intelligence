import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="MarketPulse | Terminal d'Intelligence IA",
    page_icon="📈",
    layout="wide"
)

# --- STYLE CSS : HARMONISATION ET LISIBILITÉ TOTALE ---
st.markdown("""
    <style>
    /* 1. MÉTRIQUES : Fond ardoise profond et texte blanc pur */
    div[data-testid="metric-container"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    [data-testid="stMetricValue"] {
        color: #F8FAFC !important;
        font-size: 1.8rem !important;
        font-weight: 700;
    }
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 1rem !important;
    }

    /* 2. FLUX GLOBAL (EXPANDERS) */
    .stExpander {
        border: 1px solid #334155 !important;
        background-color: #0F172A !important;
        border-radius: 8px !important;
        margin-bottom: 10px !important;
    }
    
    /* Couleur du bandeau (summary) : @utilisateur | Date */
    .stExpander summary p {
        color: #F8FAFC !important;
        font-weight: 600 !important;
    }
    
    /* Couleur du texte à l'intérieur de l'analyse (le tweet) */
    .stExpander div[data-testid="stExpanderDetails"] p {
        color: #F1F5F9 !important;
        font-size: 1rem !important;
        line-height: 1.6 !important;
    }
    
    /* Couleur spécifique pour les ID de tweets (captions) */
    .stExpander [data-testid="stCaptionContainer"] p {
        color: #94A3B8 !important;
        font-size: 0.85rem !important;
    }
    
    /* Visibilité de l'icône de flèche */
    .stExpander summary svg {
        fill: #F8FAFC !important;
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
    except Exception as e:
        st.error(f"Erreur de configuration : {e}")
        return None

db = init_db()

# --- CHARGEMENT DES DONNÉES ---
def load_data():
    if db is None: return []
    # On récupère les 100 dernières entrées basées sur ton index
    docs = db.collection('veilles_financieres').order_by(
        'date', direction=firestore.Query.DESCENDING
    ).limit(100).stream()
    return [doc.to_dict() for doc in docs]

raw_data = load_data()

if not raw_data:
    st.title("📉 MarketPulse")
    st.info("Connexion établie avec Firestore. En attente de la première ingestion de données...")
else:
    # 1. Préparation des données
    df = pd.DataFrame(raw_data)
    df['dt'] = pd.to_datetime(df['date'])
    df['jour'] = df['dt'].dt.date

    # --- HEADER & MÉTRIQUES ---
    st.title("📉 MarketPulse")
    st.caption("Intelligence de marché automatisée | Moteur : Gemini 2.5 Flash")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Analyses", len(df))
    with m2:
        st.metric("Sources Actives", len(df['source'].unique()))
    with m3:
        # Nettoyage des tickers pour le calcul du top
        all_tickers = df.explode('tickers')['tickers'].dropna().str.replace('$', '', regex=False)
        top_val = f"${all_tickers.mode()[0]}" if not all_tickers.empty else "N/A"
        st.metric("Ticker le plus cité", top_val)
    with m4:
        st.metric("Dernier Scan", df['dt'].iloc[0].strftime("%H:%M:%S"))

    st.markdown("---")

    # --- SECTION VISUALISATIONS ---
    col_v1, col_v2 = st.columns([2, 1])

    with col_v1:
        st.subheader("🔥 Concentration des Tickers")
        df_tickers = df.explode('tickers').dropna()
        if not df_tickers.empty:
            counts = df_tickers['tickers'].value_counts().reset_index()
            counts.columns = ['Ticker', 'Mentions']
            fig_bar = px.bar(
                counts.head(12), 
                x='Mentions', y='Ticker', 
                orientation='h',
                color='Mentions',
                color_continuous_scale='Blues',
                template="plotly_dark"
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.write("Aucun ticker détecté.")

    with col_v2:
        st.subheader("🗣️ Part de Voix")
        src_counts = df['source'].value_counts().reset_index()
        src_counts.columns = ['Auteur', 'Nombre']
        fig_pie = px.pie(
            src_counts, values='Nombre', names='Auteur', 
            hole=0.4, template="plotly_dark"
        )
        fig_pie.update_layout(margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    # Graphique de volume temporel
    st.subheader("📅 Intensité de l'Activité")
    daily_vol = df.groupby('jour').size().reset_index(name='Volume')
    fig_line = px.line(daily_vol, x='jour', y='Volume', markers=True, template="plotly_dark")
    fig_line.update_traces(line_color='#636EFA')
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")

    # --- RECHERCHE ET FLUX ---
    tab_flow, tab_search = st.tabs(["📑 Flux Global", "🔍 Recherche par Ticker"])

    with tab_flow:
        st.sidebar.header("Filtres")
        sources_list = sorted(df['source'].unique())
        selected = st.sidebar.multiselect("Analystes à afficher", sources_list, default=sources_list)
        
        df_display = df[df['source'].isin(selected)]
        
        for _, row in df_display.iterrows():
            with st.expander(f"@{row['source']} | {row['dt'].strftime('%d/%m %H:%M')}"):
                if row.get('tickers'):
                    st.write(f"**Focus :** {', '.join(row['tickers'])}")
                st.write(row['texte'])
                st.caption(f"ID : {row['id']}")

    with tab_search:
        st.write("### Rechercher une thèse spécifique")
        query = st.text_input("Symbole (ex: NVDA, MU, BTC)").upper().strip().replace('$', '')
        
        if query:
            def check_ticker(t_list, target):
                if not isinstance(t_list, list): return False
                return any(target == t.replace('$', '').upper() for t in t_list)

            results = df[df['tickers'].apply(lambda x: check_ticker(x, query))]
            
            if not results.empty:
                st.success(f"{len(results)} résultat(s) pour ${query}")
                for _, row in results.iterrows():
                    st.write(f"**{row['source']}** ({row['dt'].strftime('%d/%m')})")
                    st.write(row['texte'])
                    st.divider()
            else:
                st.warning(f"Aucune analyse trouvée pour ${query} dans l'historique récent.")