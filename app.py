import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="MarketPulse | Intelligence IA",
    page_icon="📉",
    layout="wide"
)

# --- STYLE CSS POUR LA LISIBILITÉ ---
st.markdown("""
    <style>
    /* Amélioration du contraste des métriques */
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-size: 1.8rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #A0AEC0 !important;
    }
    div[data-testid="metric-container"] {
        background-color: #1A202C;
        border: 1px solid #2D3748;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONNEXION FIRESTORE ---
@st.cache_resource
def init_db():
    try:
        # Priorité aux secrets Streamlit Cloud
        key_dict = json.loads(st.secrets["textkey"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict['project_id'])
    except:
        # Fallback local
        return firestore.Client.from_service_account_json("service-account.json")

db = init_db()

# --- CHARGEMENT DES DONNÉES ---
def load_data():
    # Utilisation du champ 'date_extraction' comme validé par ton index composite
    docs = db.collection('veilles_financieres').order_by(
        'date_extraction', direction=firestore.Query.DESCENDING
    ).limit(100).stream()
    return [doc.to_dict() for doc in docs]

raw_data = load_data()

if not raw_data:
    st.title("MarketPulse")
    st.info("Connexion établie. En attente de données...")
else:
    df = pd.DataFrame(raw_data)
    # Harmonisation des dates
    df['dt'] = pd.to_datetime(df['date_extraction'])
    
    # --- HEADER & MÉTRIQUES ---
    st.title("📉 MarketPulse")
    st.caption("Terminal d'intelligence financière alimenté par Gemini 2.5 Flash")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Analyses", len(df))
    with m2:
        st.metric("Sources", len(df['source'].unique()))
    with m3:
        # Calcul du ticker le plus cité (en ignorant le $)
        all_t = df.explode('tickers')['tickers'].dropna().str.replace('$', '', regex=False)
        top = f"${all_t.mode()[0]}" if not all_t.empty else "N/A"
        st.metric("Top Ticker", top)
    with m4:
        st.metric("MàJ", df['dt'].iloc[0].strftime("%H:%M"))

    st.markdown("---")

    # --- VISUALISATIONS ---
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("🔥 Concentration des Actifs")
        df_t = df.explode('tickers').dropna()
        if not df_t.empty:
            counts = df_t['tickers'].value_counts().reset_index()
            counts.columns = ['Ticker', 'Mentions']
            fig = px.bar(counts.head(10), x='Mentions', y='Ticker', orientation='h',
                         color='Mentions', color_continuous_scale='Blues', template="plotly_dark")
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("🗣️ Part de Voix")
        src_counts = df['source'].value_counts()
        fig_pie = px.pie(values=src_counts.values, names=src_counts.index, hole=0.4, template="plotly_dark")
        fig_pie.update_layout(margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- RECHERCHE ET FLUX ---
    st.markdown("---")
    tab1, tab2 = st.tabs(["📑 Flux Global", "🔍 Recherche Ticker"])

    with tab1:
        # Filtre latéral
        src_filter = st.multiselect("Filtrer les analystes", df['source'].unique(), default=df['source'].unique())
        for _, row in df[df['source'].isin(src_filter)].iterrows():
            with st.expander(f"@{row['source']} | {row['dt'].strftime('%d/%m %H:%M')}"):
                st.write(f"**Focus :** {', '.join(row['tickers']) if row['tickers'] else 'Macro'}")
                st.write(row['texte'])

    with tab2:
        query = st.text_input("Symbole (ex: MU, NVDA, PANW)").upper().strip().replace('$', '')
        if query:
            # On cherche si la version "nettoyée" du ticker match avec la saisie
            def contains_ticker(ticker_list, target):
                if not isinstance(ticker_list, list): return False
                clean_list = [t.replace('$', '').upper() for t in ticker_list]
                return target in clean_list

            results = df[df['tickers'].apply(lambda x: contains_ticker(x, query))]
            
            if not results.empty:
                st.success(f"{len(results)} analyses trouvées pour ${query}")
                for _, row in results.iterrows():
                    st.write(f"**{row['source']}** ({row['dt'].strftime('%d/%m')})")
                    st.write(row['texte'])
                    st.markdown("---")
            else:
                st.warning(f"Aucune mention de ${query} trouvée dans les 100 derniers tweets.")