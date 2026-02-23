import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import json
import pandas as pd

# 1. Configuration de la page
st.set_page_config(page_title="Veille Financière IA", layout="wide")

st.title("📈 Dashboard d'Intelligence Marché")
st.subheader("Analyse automatisée via Gemini 2.5 Flash")

# 2. Connexion à Firestore
# En local, on utilise le fichier JSON. En ligne, on utilisera les secrets Streamlit.
if "file_path" not in st.secrets:
    # Pour le test local, mets le chemin vers ton fichier JSON téléchargé
    key_dict = json.load(open("ton-fichier-cle.json"))
else:
    # Pour le déploiement en ligne
    key_dict = json.loads(st.secrets["textkey"])

creds = service_account.Credentials.from_service_account_info(key_dict)
db = firestore.Client(credentials=creds, project=key_dict['project_id'])

# 3. Récupération des données
def get_data():
    docs = db.collection('veilles_financieres').order_by('date_extraction', direction=firestore.Query.DESCENDING).limit(100).stream()
    data = []
    for doc in docs:
        data.append(doc.to_dict())
    return data

data = get_data()

if not data:
    st.write("Aucune donnée trouvée dans Firestore.")
else:
    df = pd.DataFrame(data)

    # 4. Filtres dans la barre latérale
    st.sidebar.header("Filtres")
    source_filter = st.sidebar.multiselect("Filtrer par auteur", options=df['source'].unique(), default=df['source'].unique())
    
    df_filtered = df[df['source'].isin(source_filter)]

    # 5. Affichage des métriques rapides
    col1, col2, col3 = st.columns(3)
    col1.metric("Analyses stockées", len(df))
    col2.metric("Dernière mise à jour", df['date_extraction'].iloc[0][:10])
    col3.metric("Sources actives", len(df['source'].unique()))

    # 6. Affichage des contenus
    st.markdown("---")
    for index, row in df_filtered.iterrows():
        with st.expander(f"{row['source']} - {row['date_extraction'][:16]}"):
            st.write(f"**Tickers détectés :** {', '.join(row['tickers']) if row['tickers'] else 'Aucun'}")
            st.write(row['texte'])
            st.caption(f"ID Document : {row['id']}")