import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd

st.set_page_config(page_title="FinSight Alpha", layout="wide")
st.title("📈 FinSight Alpha Dashboard")

@st.cache_resource
def init_db():
    # On récupère la clé depuis les secrets de Streamlit Cloud, pas un fichier local
    key_dict = json.loads(st.secrets["textkey"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    return firestore.Client(credentials=creds, project=key_dict['project_id'])

db = init_db()

def load_data():
    docs = db.collection('veilles_financieres').order_by('date', direction=firestore.Query.DESCENDING).limit(50).stream()
    return [doc.to_dict() for doc in docs]

raw_data = load_data()
if not raw_data:
    st.info("Aucune donnée dans Firestore.")
else:
    df = pd.DataFrame(raw_data)
    for _, row in df.iterrows():
        with st.expander(f"@{row['source']} - {row['date'][:16]}"):
            st.write(row['texte'])