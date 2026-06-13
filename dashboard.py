import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Paris Bike Mobility", page_icon="🚲", layout="wide")
st.title("🚲 Paris Bike Mobility Dashboard")

# 🔗 L'URL unique de ton API Gateway
URL_API = "https://h72ngjq4uc.execute-api.eu-west-3.amazonaws.com/prod"

# Fonction générique pour interroger l'API Gateway
def app_fetch_data(endpoint):
    try:
        res = requests.get(f"{URL_API}{endpoint}", timeout=10)
        if res.status_code == 200:
            return res.json()
        return None
    except:
        return None

# Onglets orientés exclusivement Équipes Métiers et Supervision
tabs = st.tabs([
    "Live Vélib",
    "Saturation — Mairie",
    "Attractivité — Commerçants",
    "Sécurité Capteurs"
])

# --- TAB 0 : LIVE VELIB ---
with tabs[0]:
    st.header("Disponibilité Vélib — Temps Réel")
    
    data_live = app_fetch_data("/velib-live")
    if data_live and "stations" in data_live:
        df = pd.DataFrame(data_live["stations"])
        
        # Harmonisation et conversion des types de données
        for col in ['available_bikes', 'available_docks', 'capacity', 'lat', 'lon', 'latitude', 'longitude']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Redondance pour s'assurer que Streamlit trouve les colonnes 'latitude' et 'longitude'
        if 'lat' in df.columns and 'latitude' not in df.columns:
            df = df.rename(columns={'lat': 'latitude'})
        if 'lon' in df.columns and 'longitude' not in df.columns:
            df = df.rename(columns={'lon': 'longitude'})
                
        c1, c2, c3 = st.columns(3)
        c1.metric("Stations Actives", data_live.get("nb_stations_live", len(df)))
        c2.metric("Vélos disponibles", int(df['available_bikes'].sum()) if 'available_bikes' in df.columns else 0)
        c3.metric("Bornettes libres", int(df['available_docks'].sum()) if 'available_docks' in df.columns else 0)
        
        # Affichage de la carte si les coordonnées sont valides
        if 'latitude' in df.columns and 'longitude' in df.columns:
            df_map = df.dropna(subset=['latitude', 'longitude'])
            if not df_map.empty:
                st.map(df_map[['latitude', 'longitude']])
            else:
                st.warning("Coordonnées géographiques vides ou invalides dans le flux.")
        else:
            st.warning("Champs de géolocalisation manquants dans le flux de données.")
            
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
        
        fig = px.pie(isc, names='zone_criticite', title="Répartition de la criticité ISC",
                     color='zone_criticite', color_discrete_map={"CRITIQUE":"red","VIGILANCE":"orange","ACCEPTABLE":"green"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(isc.head(50), use_container_width=True)
    else:
        st.error("Données de saturation indisponibles via l'API.")

# --- TAB 2 : ATTRACTIVITE ---
with tabs[2]:
    st.header("Score d'Attractivité — Commerçants")
    st.caption("Score = bike_count / baseline_avg. HIGH > 1.2 / NORMAL 0.8-1.2 / LOW < 0.8")
    
    data_attr = app_fetch_data("/area-attractiveness")
    if data_attr and "data" in data_attr:
        attr = pd.DataFrame(data_attr["data"])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("HIGH", len(attr[attr['niveau']=='HIGH']))
        c2.metric("NORMAL", len(attr[attr['niveau']=='NORMAL']))
        c3.metric("LOW", len(attr[attr['niveau']=='LOW']))
        
        fig2 = px.bar(attr.head(20), x='counter_name', y='score_attractivite', color='niveau',
                     color_discrete_map={"HIGH":"red","NORMAL":"green","LOW":"blue"}, title="Top 20 zones attractivité")
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(attr, use_container_width=True)
    else:
        st.error("Données d'attractivité indisponibles via l'API.")

# --- TAB 3 : SECURITE CAPTEURS ---
with tabs[3]:
    st.header("Inactivité Capteurs — Sécurité")
    data_inact = app_fetch_data("/sensor-inactivity")
    if data_inact and "data" in data_inact and len(data_inact["data"]) > 0:
        latest = data_inact["data"][0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total capteurs", int(latest.get('total_capteurs', 0)))
        c2.metric("Actifs", int(latest.get('capteurs_actifs', 0)))
        c3.metric("Inactifs", int(latest.get('capteurs_inactifs', 0)))
        c4.metric("Taux pannes", f"{latest.get('taux_inactivite_pct', 0)}%", delta_color="inverse")
        
        if float(latest.get('taux_inactivite_pct', 0)) > 10:
            st.error("ALERTE : Taux > 10% — vérification nécessaire sur le terrain")
        else:
            st.success("Statut des capteurs : OPÉRATIONNEL")
    else:
        st.error("Données d'inactivité indisponibles via l'API.")
