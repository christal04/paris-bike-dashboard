import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Paris Bike Mobility", page_icon="🚲", layout="wide")
st.title("🚲 Paris Bike Mobility Dashboard")

# 🔗 L'URL unique de ton API Gateway (SANS le slash / à la fin)
URL_API = "https://h72ngjq4uc.execute-api.eu-west-3.amazonaws.com/prod"

# Fonction générique pour interroger ton API
def app_fetch_data(endpoint):
    try:
        res = requests.get(f"{URL_API}{endpoint}", timeout=10)
        if res.status_code == 200:
            return res.json()
        return None
    except:
        return None

tabs = st.tabs([
    "Live Velib",
    "Saturation — Mairie",
    "Attractivite — Commercants",
    "Securite Capteurs",
    "Etat de la Pipeline",
    "RGPD & Lineage"
])

# --- TAB 0 : LIVE VELIB ---
with tabs[0]:
    st.header("Disponibilite Velib — temps reel")
    st.caption("Mis a jour toutes les 5 minutes via Kinesis")
    
    data_live = app_fetch_data("/velib-live")
    if data_live and "stations" in data_live:
        df = pd.DataFrame(data_live["stations"])
        
        for col in ['available_bikes','available_docks','capacity']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        c1, c2, c3 = st.columns(3)
        c1.metric("Stations Actives", data_live.get("nb_stations_live", len(df)))
        c2.metric("Velos disponibles", int(df['available_bikes'].sum()) if 'available_bikes' in df.columns else 0)
        c3.metric("Bornettes libres", int(df['available_docks'].sum()) if 'available_docks' in df.columns else 0)
        
        if 'lat' in df.columns and 'lon' in df.columns:
            df_map = df.dropna(subset=['lat','lon']).rename(columns={'lat':'latitude','lon':'longitude'})
            st.map(df_map[['latitude','longitude']])
            st.caption("Positions approximees — conformite RGPD")
        st.dataframe(df.head(50), use_container_width=True)
    else:
        st.error("Flux streaming indisponible via l'API.")

# --- TAB 1 : SATURATION ---
with tabs[1]:
    st.header("Indice de Saturation Cycliste — Mairie")
    st.caption("ISC = (Taux saturation x Score trafic) / 100")
    
    data_sat = app_fetch_data("/station-saturation")
    if data_sat and "stations" in data_sat:
        isc = pd.DataFrame(data_sat["stations"])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("CRITIQUE (>=50)", len(isc[isc['zone_criticite']=='CRITIQUE']))
        c2.metric("VIGILANCE (25-49)", len(isc[isc['zone_criticite']=='VIGILANCE']))
        c3.metric("ACCEPTABLE (<25)", len(isc[isc['zone_criticite']=='ACCEPTABLE']))
        
        fig = px.pie(isc, names='zone_criticite', title="Repartition de la criticite ISC",
                     color='zone_criticite', color_discrete_map={"CRITIQUE":"red","VIGILANCE":"orange","ACCEPTABLE":"green"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(isc.head(50), use_container_width=True)
    else:
        st.error("Donnees de saturation indisponibles via l'API.")

# --- TAB 2 : ATTRACTIVITE ---
with tabs[2]:
    st.header("Score d'Attractivite — Commercants")
    st.caption("Score = bike_count / baseline_avg. HIGH > 1.2 / NORMAL 0.8-1.2 / LOW < 0.8")
    
    data_attr = app_fetch_data("/area-attractiveness")
    if data_attr and "data" in data_attr:
        attr = pd.DataFrame(data_attr["data"])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("HIGH", len(attr[attr['niveau']=='HIGH']))
        c2.metric("NORMAL", len(attr[attr['niveau']=='NORMAL']))
        c3.metric("LOW", len(attr[attr['niveau']=='LOW']))
        
        fig2 = px.bar(attr.head(20), x='counter_name', y='score_attractivite', color='niveau',
                     color_discrete_map={"HIGH":"red","NORMAL":"green","LOW":"blue"}, title="Top 20 zones attractivite")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.error("Donnees d'attractivite indisponibles via l'API.")

# --- TAB 3 : SECURITE CAPTEURS ---
with tabs[3]:
    st.header("Inactivite Capteurs — Securite")
    data_inact = app_fetch_data("/sensor-inactivity")
    if data_inact and "data" in data_inact and len(data_inact["data"]) > 0:
        latest = data_inact["data"][0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total capteurs", int(latest.get('total_capteurs', 0)))
        c2.metric("Actifs", int(latest.get('capteurs_actifs', 0)))
        c3.metric("Inactifs", int(latest.get('capteurs_inactifs', 0)))
        c4.metric("Taux pannes", f"{latest.get('taux_inactivite_pct', 0)}%", delta_color="inverse")
        
        if float(latest.get('taux_inactivite_pct', 0)) > 10:
            st.error("ALERTE : Taux > 10% — verification necessaire sur le terrain")
        else:
            st.success("Statut des capteurs : OPERATIONNEL")
    else:
        st.error("Donnees d'inactivite indisponibles via l'API.")

# --- TAB 4 : PIPELINE ---
with tabs[4]:
    st.header("Etat de la Pipeline")
    st.markdown("""
    **Services actifs :**
    - **EventBridge** : Planification Batch 2h UTC / Alertes toutes les 5 min
    - **Step Functions** : Orchestration du workflow `pipeline-velo-batch-daily`
    - **Kinesis** : Collecte des donnees temps reel `velib-realtime-stream`
    - **Glue** : Transformation couches Silver (`silver-transform`) et Gold (`gold-kpis`)
    - **DynamoDB** : Stockage final NoSQL de la couche Gold
    - **API Gateway** : Exposition securisee via HTTPS sans partage de clefs credentials
    """)

# --- TAB 5 : RGPD ---
with tabs[5]:
    st.header("Conformite RGPD & Gouvernance")
    st.markdown("""
    **Niveau de risque global : TRÈS FAIBLE** (Donnees ouvertes et anonymes, aucun identifiant personnel).
    
    | Couche | Mesure de Securite | Justification Technique |
    |---|---|---|
    | **Bronze** | Chiffrement natif SSE-S3 | Protection des fichiers bruts au repos |
    | **Silver** | GPS arrondi a 2 decimales | Floutage et generalisation spatiale volontaire |
    | **Gold** | Pas de donnees unitaires | Uniquement des agregats de performance globale |
    | **API Gateway** | Pas d'acces direct aux tables | Couche d'abstraction hermetique |
    """)