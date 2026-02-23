import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd

st.set_page_config(page_title="FinSight Alpha", layout="wide")
st.title("📈 FinSight Alpha Dashboard")

@st.cache_resource
def init_db():
    # Utilise le secret 'textkey' configuré sur Streamlit Cloud
    key_dict = json.loads(st.secrets["textkey"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    return firestore.Client(credentials=creds, project=key_dict['project_id'])

db = init_db()

def load_data():
    # On trie sur 'date' pour correspondre au Bot et à l'Index
    docs = db.collection('veilles_financieres').order_by('date', direction=firestore.Query.DESCENDING).limit(50).stream()
    return [doc.to_dict() for doc in docs]

try:
    raw_data = load_data()
    if not raw_data:
        st.info("Aucune donnée dans Firestore. Lancez le Bot une fois.")
    else:
        df = pd.DataFrame(raw_data)
        st.sidebar.header("Filtres")
        sources = df['source'].unique()
        selected = st.sidebar.multiselect("Analystes", sources, default=sources)
        
        for _, row in df[df['source'].isin(selected)].iterrows():
            with st.expander(f"@{row['source']} - {row['date'][:16].replace('T', ' ')}"):
                if row.get('tickers'):
                    st.write(f"**Tickers :** {', '.join(row['tickers'])}")
                st.write(row['texte'])
except Exception as e:
    st.error(f"Erreur de synchronisation : {e}")