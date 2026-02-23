import http.client
import json
import os
import smtplib
from email.mime.text import MIMEText
import google.generativeai as genai
from google.cloud import firestore
import yfinance as yf
from datetime import datetime
import functions_framework

# Initialisation Firestore
db = firestore.Client()
cache_prix = {}

def recuperer_prix(ticker):
    symbol = ticker.replace('$', '').strip()
    if symbol in cache_prix:
        return cache_prix[symbol]
    try:
        stock = yf.Ticker(symbol)
        price = stock.fast_info['last_price']
        cache_prix[symbol] = price
        return price
    except:
        return None

def extraire_donnees(entry):
    # --- FILTRE ANTI-PUB ---
    # On ignore tout ce qui contient "promoted" dans l'ID ou possède des métadonnées sponsorisées
    entry_id = str(entry.get('entryId', ''))
    if "promoted" in entry_id.lower() or "promotedMetadata" in str(entry):
        return None

    res = entry.get('content', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})
    if 'tweet' in res: res = res['tweet']
    legacy = res.get('legacy', {})
    
    # Filtre les réponses
    if legacy.get('in_reply_to_screen_name') is not None: return None
    
    # Texte (Priorité Note Tweet)
    texte = res.get('note_tweet', {}).get('note_tweet_results', {}).get('result', {}).get('text')
    if not texte: texte = legacy.get('full_text')
    
    # Filtre les retweets
    if not texte or texte.startswith("RT @"): return None
    
    tickers = list(set([word.upper() for word in texte.split() if word.startswith('$') and word[1:].isalpha()]))
    
    return {
        "id": entry_id,
        "texte": texte, 
        "tickers": tickers, 
        "date_extraction": datetime.now().isoformat()
    }

@functions_framework.http
def lancer_analyse(request):
    comptes_config = {
        '*******': '*******'
    }
    
    cle_rapidapi = os.environ.get('CLE_RAPIDAPI')
    cle_gemini = os.environ.get('CLE_API_GEMINI')
    email_exp = os.environ.get('EMAIL_EXPEDITEUR')
    mdp_app = os.environ.get('MOT_DE_PASSE_APP')
    email_dest = os.environ.get('EMAIL_DESTINATAIRE')

    donnees_globales = ""
    
    for nom, uid in comptes_config.items():
        try:
            conn = http.client.HTTPSConnection("twitter241.p.rapidapi.com", timeout=15)
            conn.request("GET", f"/user-tweets?user={uid}&count=10", headers={'x-rapidapi-key': cle_rapidapi})
            res = conn.getresponse()
            
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                instructions = data.get('result', {}).get('timeline', {}).get('instructions', [])
                
                v_count = 0
                for inst in instructions:
                    if inst.get('type') == 'TimelineAddEntries':
                        for entry in inst.get('entries', []):
                            if v_count >= 5: break
                            
                            info = extraire_donnees(entry)
                            if info:
                                p_str = ""
                                for t in info['tickers']:
                                    p = recuperer_prix(t)
                                    if p: p_str += f" ({t}: {p:.2f}$)"
                                
                                info['source'] = nom
                                db.collection('veilles_financieres').document(info['id']).set(info)
                                
                                donnees_globales += f"Source @{nom}{p_str}:\n{info['texte']}\n\n"
                                v_count += 1
            conn.close()
        except: continue

    if donnees_globales:
        try:
            genai.configure(api_key=cle_gemini)
            # --- UTILISATION STRICTE 2.5 FLASH ---
            modele = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = (
                "Tu es un analyste financier pragmatique. Pour chaque thématique majeure identifiée, "
                "fournis strictement : 1) Une synthèse factuelle, 2) Une explication technique des mécanismes, "
                "3) Les opportunités identifiées. Aborde la patience et la discipline uniquement sous l'angle "
                "du timing de marché et de la gestion de risque. Interdiction de toute rhétorique motivationnelle.\n\n"
                "Données :\n" + donnees_globales
            )
            
            corps_final = modele.generate_content(prompt).text
        except Exception as e:
            corps_final = f"ERREUR IA : {e}\n\nDONNÉES BRUTES :\n{donnees_globales}"

        # Envoi Mail
        try:
            msg = MIMEText(corps_final)
            msg['Subject'] = f"Analyse Marché - {datetime.now().strftime('%d/%m %H:%M')}"
            msg['From'], msg['To'] = email_exp, email_dest
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(email_exp, mdp_app)
                server.send_message(msg)
            return 'OK'
        except Exception as e:
            return f'Erreur SMTP : {e}'
            
    return 'OK - Aucune donnée'