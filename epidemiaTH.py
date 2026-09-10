import io
import json
import unicodedata
import zipfile

# CONFIGURATION DU BACKEND MATPLOTLIB (POUR VISUALISATIONS HD ET EXPORTS RAPPORT)
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

import os
import random
import numpy as np
import pandas as pd
import streamlit as st
from scipy.integrate import odeint
from sqlalchemy import create_engine, inspect, text

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

try:
    import folium
    from folium.plugins import TimestampedGeoJson
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except Exception:
    HAS_FOLIUM = False

# CONFIGURATION DE LA PAGE STREAMLIT
st.set_page_config(
    page_title="Epidemia - Dashboard Épidémiologique RD Congo",
    page_icon="🦠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS Adaptatif (Mode Clair & Mode Sombre)
st.markdown("""
<style>
    :root {
        --card-bg: #ffffff;
        --card-border: #cbd5e1;
        --card-text: #0f172a;
        --card-title: #64748b;
        --header-bg: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #1e3a8a 100%);
        --header-title: #ffffff;
        --header-sub: #e0f2fe;
    }

    @media (prefers-color-scheme: dark) {
        :root {
            --card-bg: #1e293b;
            --card-border: #334155;
            --card-text: #f8fafc;
            --card-title: #94a3b8;
            --header-bg: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
            --header-title: #ffffff;
            --header-sub: #cfd8dc;
        }
    }

    /* Main Header */
    .main-header {
        background: var(--header-bg);
        padding: 1.8rem 2rem;
        border-radius: 12px;
        color: var(--header-title);
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.12);
    }
    .main-header h1 {
        color: var(--header-title) !important;
        font-weight: 700;
        margin-bottom: 0.3rem;
        font-size: 2.2rem;
    }
    .main-header p {
        color: var(--header-sub) !important;
        font-size: 1.05rem;
        margin-bottom: 0;
    }
    
    /* Dynamic Metric Cards */
    .metric-card {
        background-color: var(--card-bg, var(--secondary-background-color));
        border: 1px solid var(--card-border, var(--border-color));
        border-radius: 10px;
        padding: 1.2rem;
        height: 148px;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .metric-title {
        color: var(--card-title);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        min-height: 2.1em;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0.25rem;
    }
    .metric-value {
        color: var(--card-text, var(--text-color));
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
        min-height: 2.2rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .metric-sub {
        color: #0284c7;
        font-size: 0.85rem;
        margin-top: 0.4rem;
        font-weight: 600;
        min-height: 1.1rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* Couleur commune de tous les boutons d'action */
    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"] > button {
        width: 100%;
        min-height: 48px;
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: #ffffff !important;
        font-weight: 700;
    }
    div[data-testid="stButton"] > button:hover,
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #d93636 !important;
        border-color: #d93636 !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 0. RÉFÉRENTIEL DES COULEURS ET SYMBOLES PAR PROVINCE (RD CONGO)
# ==============================================================================

COULEURS_PROVINCES_RDC = {
    "sud-kivu": {"couleur": "#2563eb", "nom": "Sud-Kivu", "nom_couleur": "Bleu Royal"},
    "nord-kivu": {"couleur": "#16a34a", "nom": "Nord-Kivu", "nom_couleur": "Vert Émeraude"},
    "kinshasa": {"couleur": "#7c3aed", "nom": "Kinshasa", "nom_couleur": "Violet Impérial"},
    "kongo-central": {"couleur": "#0891b2", "nom": "Kongo-Central", "nom_couleur": "Cyan Océan"},
    "haut-katanga": {"couleur": "#d97706", "nom": "Haut-Katanga", "nom_couleur": "Ambre Doré"},
    "lualaba": {"couleur": "#b45309", "nom": "Lualaba", "nom_couleur": "Bronze Cuivré"},
    "ituri": {"couleur": "#047857", "nom": "Ituri", "nom_couleur": "Vert Forêt"},
    "kasai": {"couleur": "#db2777", "nom": "Kasaï", "nom_couleur": "Rose Magenta"},
    "kasai-central": {"couleur": "#9333ea", "nom": "Kasaï-Central", "nom_couleur": "Pourpre Vif"},
    "kasai-oriental": {"couleur": "#e11d48", "nom": "Kasaï-Oriental", "nom_couleur": "Rouge Rubis"},
    "kwilu": {"couleur": "#65a30d", "nom": "Kwilu", "nom_couleur": "Vert Lime"},
    "kwango": {"couleur": "#0d9488", "nom": "Kwango", "nom_couleur": "Sarcelle / Teal"},
    "mai-ndombe": {"couleur": "#1e40af", "nom": "Maï-Ndombe", "nom_couleur": "Bleu Nuit"},
    "maniema": {"couleur": "#a16207", "nom": "Maniema", "nom_couleur": "Ocre Brun"},
    "tshopo": {"couleur": "#0284c7", "nom": "Tshopo", "nom_couleur": "Bleu Ciel"},
    "haut-uele": {"couleur": "#ea580c", "nom": "Haut-Uele", "nom_couleur": "Orange Corail"},
    "bas-uele": {"couleur": "#2563eb", "nom": "Bas-Uele", "nom_couleur": "Bleu Royal"},
    "mongala": {"couleur": "#059669", "nom": "Mongala", "nom_couleur": "Vert Menthe"},
    "nord-ubangi": {"couleur": "#8b5cf6", "nom": "Nord-Ubangi", "nom_couleur": "Lilas / Mauve"},
    "sud-ubangi": {"couleur": "#15803d", "nom": "Sud-Ubangi", "nom_couleur": "Vert Prairie"},
    "tanganyika": {"couleur": "#4338ca", "nom": "Tanganyika", "nom_couleur": "Indigo Lacustre"},
    "lomami": {"couleur": "#c026d3", "nom": "Lomami", "nom_couleur": "Fuchsia"},
    "sankuru": {"couleur": "#4d7c0f", "nom": "Sankuru", "nom_couleur": "Vert Olive"},
    "haut-lomami": {"couleur": "#c2410c", "nom": "Haut-Lomami", "nom_couleur": "Terre Cuite"},
    "tshuapa": {"couleur": "#166534", "nom": "Tshuapa", "nom_couleur": "Vert Mousse"},
    "equateur": {"couleur": "#0e7490", "nom": "Équateur", "nom_couleur": "Cyan Profond"}
}

def normaliser_nom_province(texte):
    """Normalise le nom de la province (minuscule, sans accents, sans tirets/espaces hétérogènes)."""
    if not texte:
        return ""
    texte_str = str(texte).strip()
    norm = unicodedata.normalize('NFKD', texte_str).encode('ASCII', 'ignore').decode('utf-8')
    return norm.strip().lower().replace("_", "-").replace(" ", "-")

def obtenir_couleur_province(nom_province):
    """Retourne la couleur hexadécimale distinctive propre aux symboles de chaque province."""
    cle = normaliser_nom_province(nom_province)
    if cle in COULEURS_PROVINCES_RDC:
        return COULEURS_PROVINCES_RDC[cle]["couleur"]
    for k, v in COULEURS_PROVINCES_RDC.items():
        if k in cle or cle in k:
            return v["couleur"]
    # Palette de repli déterministe pour toute province personnalisée
    palette_fallback = ["#2563eb", "#16a34a", "#7c3aed", "#d97706", "#0891b2", "#db2777", "#ea580c", "#059669"]
    h = sum(ord(c) for c in str(nom_province))
    return palette_fallback[h % len(palette_fallback)]

def obtenir_nom_couleur_province(nom_province):
    """Retourne le libellé de la couleur de la province."""
    cle = normaliser_nom_province(nom_province)
    if cle in COULEURS_PROVINCES_RDC:
        return COULEURS_PROVINCES_RDC[cle]["nom_couleur"]
    for k, v in COULEURS_PROVINCES_RDC.items():
        if k in cle or cle in k:
            return v["nom_couleur"]
    return "Couleur Thématique"



# 1. GESTION DE LA CONNEXION À LA BASE DE DONNÉES MYSQL

@st.cache_resource
def get_db_engine(user, password, host, port, dbname):
    """Crée et met en cache la connexion SQLAlchemy vers MySQL."""
    conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=latin1"
    return create_engine(conn_str, pool_pre_ping=True)

def me_connecter_base():
    """Formulaire sidebar / initialisation de la base de données."""
    st.sidebar.markdown("Connexion MySQL")
    
    with st.sidebar.expander("Paramètres MySQL", expanded=False):
        db_host = st.text_input("Hôte", value="localhost")
        db_port = st.text_input("Port", value="3306")
        db_user = st.text_input("Utilisateur", value="root")
        db_password = st.text_input("Mot de passe", value="", type="password")
        db_name = st.text_input("Base de données", value="epidemia")
        
    try:
        engine = get_db_engine(db_user, db_password, db_host, db_port, db_name)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # st.sidebar.success("Connexion MySQL réussie")
        return engine
    except Exception as e:
        st.sidebar.error(f"Échec de connexion : {e}")
        st.error(f"Impossible de se connecter à la base de données MySQL `{db_name}` sur {db_host}:{db_port}. Veuillez vérifier vos identifiants dans la sidebar.")
        return None


# 2. REQUÊTES SQL ET CHARGEMENT DYNAMIQUE DES DONNÉES

def trouver_nom_colonne_infra(engine):
    """Détermine le nom exact de la colonne d'infrastructure dans la table infrastructures."""
    try:
        inspector = inspect(engine)
        colonnes = [c['name'] for c in inspector.get_columns('infrastructures')]
        candidats = ['nom_infrastructure', 'nomInfra', 'nom_infra', 'nom_structure', 'nom', 'nom_est']
        for c in candidats:
            if c in colonnes:
                return c
        return colonnes[1] if len(colonnes) > 1 else colonnes[0]
    except Exception:
        return 'nom_infrastructure'

@st.cache_data(ttl=300)
def charger_provinces(_engine):
    """Charge dynamiquement la liste des provinces uniques depuis zonesante."""
    query = text("SELECT DISTINCT province FROM zonesante WHERE province IS NOT NULL AND TRIM(province) != '' ORDER BY province")
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df['province'].str.strip().dropna().unique().tolist()

@st.cache_data(ttl=300)
def charger_maladies(_engine):
    """Charge la table maladie complète."""
    query = text("SELECT * FROM maladie")
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=300)
def charger_infrastructures_par_province(_engine, province_selectionnee):
    """Charge dynamiquement les infrastructures filtrées par la province choisie."""
    colonne_infra = trouver_nom_colonne_infra(_engine)
    query = text(f"""
        SELECT DISTINCT i.{colonne_infra} AS nom_infra
        FROM infrastructures i
        JOIN zonesante z ON i.idZone = z.idZone
        WHERE LOWER(TRIM(z.province)) = LOWER(TRIM(:prov))
          AND i.{colonne_infra} IS NOT NULL 
          AND TRIM(i.{colonne_infra}) != ''
        ORDER BY i.{colonne_infra}
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"prov": province_selectionnee})
    return df['nom_infra'].str.strip().dropna().tolist()


@st.cache_data(ttl=300)
def charger_toutes_zones_infrastructures(_engine):
    """Charge dynamiquement l'ensemble des zones de santé et infrastructures de référence géolocalisées de toutes les provinces."""
    colonne_infra = trouver_nom_colonne_infra(_engine)
    query = text(f"""
        SELECT 
            z.idZone,
            z.NomZone AS nomZone,
            z.province,
            z.population_2026,
            COALESCE(z.capacite_totale, 50) AS lits_reels,
            i.{colonne_infra} AS nom_infra_ref,
            i.latitude AS latitude_infra,
            i.longitude AS longitude_infra
        FROM zonesante z
        JOIN infrastructures i ON z.idZone = i.idZone
        WHERE i.latitude IS NOT NULL AND i.longitude IS NOT NULL
        GROUP BY z.idZone, z.NomZone, z.province, z.population_2026, z.capacite_totale
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df['latitude_infra'] = pd.to_numeric(df['latitude_infra'], errors='coerce')
    df['longitude_infra'] = pd.to_numeric(df['longitude_infra'], errors='coerce')
    return df.dropna(subset=['latitude_infra', 'longitude_infra']).reset_index(drop=True)


# 3. OUTILS DE CALCUL ÉPIDÉMIOLOGIQUE & MOBILITÉ

def calculer_distance_haversine(lat1, lon1, lat2, lon2):
    """Calcule la distance orthodromique (km) entre deux coordonnées."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0)**2
    return R * (2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)))

def extract_t0_num(t0_str):
    """Extrait la valeur numérique du jour t0 (ex: 'Jour 15' -> 15, 'Non touchée' -> 999)."""
    if isinstance(t0_str, (int, float)):
        return int(t0_str)
    if "Jour" in str(t0_str):
        try:
            return int(str(t0_str).replace("Jour", "").strip())
        except ValueError:
            return 999
    return 999

def generer_matrice_mobilite_infrastructures(df_z, theta=1e-5, gamma_dist=2.0):
    """Génère la matrice de mobilité gravitaire inter-infrastructures."""
    K = len(df_z)
    M = np.zeros((K, K))
    lats = df_z['latitude_infra'].values
    lons = df_z['longitude_infra'].values
    pops = df_z['population_2026'].values

    for i in range(K):
        for j in range(K):
            if i != j:
                dist_km = max(calculer_distance_haversine(lats[i], lons[i], lats[j], lons[j]), 1.0)
                flux = theta * (pops[i] * pops[j]) / (dist_km ** gamma_dist)
                M[i, j] = flux / max(pops[i], 1.0)
    return M

def resoudre_simulation_seir_zone(idx_start, df_zones_p, N_vec, M, t_total, est_seir, beta_base, gamma_base, sigma_base, taux_hosp, nom_maladie, R0_base, D_base, E_base, nom_province, mode_selection="Aléatoire"):
    """Résout le modèle différentiel pour un foyer initial donné (idx_start) et retourne les données complètes."""
    K = len(df_zones_p)
    if est_seir:
        def modele_ode(y, t):
            S, E, I, R = y[0:K], y[K:2*K], y[2*K:3*K], y[3*K:4*K]
            dS, dE, dI, dR = np.zeros(K), np.zeros(K), np.zeros(K), np.zeros(K)
            for i in range(K):
                inf_loc = beta_base * S[i] * max(0, I[i]) / max(1, N_vec[i])
                sortants_E = np.sum(M[i, :]) * max(0, E[i])
                entrants_E = np.dot(M[:, i], np.maximum(0, E))
                sortants_I = np.sum(M[i, :]) * max(0, I[i])
                entrants_I = np.dot(M[:, i], np.maximum(0, I))
                
                dS[i] = -inf_loc
                dE[i] = inf_loc - (sigma_base * E[i]) - sortants_E + entrants_E
                dI[i] = (sigma_base * E[i]) - (gamma_base * I[i]) - sortants_I + entrants_I
                dR[i] = gamma_base * I[i]
            return np.concatenate([dS, dE, dI, dR])

        S0 = np.copy(N_vec)
        E0 = np.zeros(K)
        I0 = np.zeros(K)
        R0_init = np.zeros(K)
        I0[idx_start] = 1.0
        S0[idx_start] -= 1.0

        y0 = np.concatenate([S0, E0, I0, R0_init])
        res = odeint(modele_ode, y0, t_total)
        S_mat, E_mat, I_mat, R_mat = res[:, 0:K], res[:, K:2*K], res[:, 2*K:3*K], res[:, 3*K:4*K]

    else:
        def modele_ode(y, t):
            S, I, R = y[0:K], y[K:2*K], y[2*K:3*K]
            dS, dI, dR = np.zeros(K), np.zeros(K), np.zeros(K)
            for i in range(K):
                inf_loc = beta_base * S[i] * max(0, I[i]) / max(1, N_vec[i])
                sortants_I = np.sum(M[i, :]) * max(0, I[i])
                entrants_I = np.dot(M[:, i], np.maximum(0, I))
                
                dS[i] = -inf_loc
                dI[i] = inf_loc - (gamma_base * I[i]) - sortants_I + entrants_I
                dR[i] = gamma_base * I[i]
            return np.concatenate([dS, dI, dR])

        S0 = np.copy(N_vec)
        I0 = np.zeros(K)
        R0_init = np.zeros(K)
        I0[idx_start] = 1.0
        S0[idx_start] -= 1.0

        y0 = np.concatenate([S0, I0, R0_init])
        res = odeint(modele_ode, y0, t_total)
        S_mat, I_mat, R_mat = res[:, 0:K], res[:, K:2*K], res[:, 2*K:3*K]
        E_mat = np.zeros_like(S_mat)

    # Traitement des résultats pour ce foyer
    liste_synthese = []
    liste_journaliere_longue = []
    dict_infectes_matrice = {"Jour": [f"Jour {int(t)}" for t in t_total]}

    for i in range(K):
        nom_z = df_zones_p.loc[i, 'nomZone']
        infra_ref = df_zones_p.loc[i, 'nom_infra_ref']
        pop_z = int(N_vec[i])
        lits_z = round(df_zones_p.loc[i, 'lits_reels'])

        I_serie = I_mat[:, i]
        E_serie = E_mat[:, i]
        S_serie = S_mat[:, i]
        R_serie = R_mat[:, i]

        if i == idx_start:
            t0_jour_val = 1
        else:
            jours_seuil = np.where(I_serie >= 0.5)[0]
            t0_jour_val = int(t_total[jours_seuil[0]]) if len(jours_seuil) > 0 else 999

        t0_str = f"Jour {t0_jour_val}" if t0_jour_val != 999 else "Non touchée"

        I_arr_list, E_arr_list, S_arr_list, R_arr_list = [], [], [], []

        for j_idx, jour_val in enumerate(t_total):
            if int(jour_val) < t0_jour_val:
                s_arr, e_arr, i_arr, r_arr = pop_z, 0, 0, 0
            else:
                s_val, e_val, i_val, r_val = S_serie[j_idx], E_serie[j_idx], I_serie[j_idx], R_serie[j_idx]
                s_arr = max(0, int(round(s_val)))
                e_arr = max(0, int(round(e_val)))
                i_arr = max(0, int(round(i_val)))
                r_arr = max(0, int(round(r_val)))

                somme_seir = s_arr + e_arr + i_arr + r_arr
                if somme_seir != pop_z:
                    s_arr += (pop_z - somme_seir)

            S_arr_list.append(max(0, s_arr))
            E_arr_list.append(max(0, e_arr))
            I_arr_list.append(max(0, i_arr))
            R_arr_list.append(max(0, r_arr))

            lits_occupes = int(round(max(0, i_arr) * taux_hosp))

            record_day = {
                "Jour": int(jour_val),
                "Zone de Santé": nom_z,
                "Province": df_zones_p.loc[i, 'province'],
                "Susceptibles (S)": max(0, s_arr),
                "Infectés (I)": max(0, i_arr),
                "Rétablis (R)": max(0, r_arr),
                "Lits Occupés": lits_occupes
            }
            if est_seir:
                record_day["Exposés (E)"] = max(0, e_arr)

            liste_journaliere_longue.append(record_day)

        I_max_reel = max(I_arr_list) if I_arr_list else 0
        idx_pic = np.argmax(I_arr_list) if I_arr_list else 0
        jour_pic = int(t_total[idx_pic]) if len(t_total) > idx_pic else 1

        cap_requise = round(I_max_reel * taux_hosp)
        deficit = max(0, cap_requise - lits_z)

        liste_synthese.append({
            "Zone de Santé": nom_z,
            "Province": df_zones_p.loc[i, 'province'],
            "Infrastructure Référente": infra_ref,
            "Population": pop_z,
            "I0": 1 if i == idx_start else 0,
            "t0": t0_str,
            "Cpt Lits": lits_z,
            "I_max": I_max_reel,
            "Jour du Pic": f"Jour {jour_pic}",
            "CapRequisPic": cap_requise,
            "Déficit cpt": deficit,
            "Latitude": df_zones_p.loc[i, 'latitude_infra'],
            "Longitude": df_zones_p.loc[i, 'longitude_infra'],
            "est_foyer": (i == idx_start)
        })

        dict_infectes_matrice[nom_z] = I_arr_list

    df_synth = pd.DataFrame(liste_synthese)
    df_long = pd.DataFrame(liste_journaliere_longue)
    df_matrice = pd.DataFrame(dict_infectes_matrice)

    group_cols = ["Jour"]
    df_prov_daily = df_long.groupby(group_cols)[["Susceptibles (S)", "Infectés (I)", "Rétablis (R)", "Lits Occupés"]].sum().reset_index()
    if est_seir and "Exposés (E)" in df_long.columns:
        df_prov_daily["Exposés (E)"] = df_long.groupby(group_cols)["Exposés (E)"].sum().values

    infra_exacte = df_zones_p.iloc[idx_start]['nom_infra_ref']
    zone_depart_nom = df_zones_p.iloc[idx_start]['nomZone']

    return {
        "df_synth": df_synth,
        "df_long": df_long,
        "df_matrice": df_matrice,
        "df_prov_daily": df_prov_daily,
        "maladie_meta": {
            "Nom": nom_maladie,
            "Ro": R0_base,
            "D": D_base,
            "E": E_base,
            "Modele": "SEIR" if est_seir else "SIR",
            "TauxHosp": taux_hosp
        },
        "province": nom_province,
        "infra_depart": infra_exacte,
        "zone_depart": zone_depart_nom,
        "idx_start": idx_start,
        "mode_selection_epicentre": mode_selection
    }


def generer_analyse_sensibilite_provinciale_moyenne(simulations_foyers, pas_jours=10, pas_taux=0.05, alpha_soins=0.8):
    """Calcule le tableau croisé et la matrice plate de sensibilité moyenne sur l'ensemble des foyers simulés,
    en faisant varier dynamiquement le nombre de personnes rétablies (R), infectées (I) et susceptibles (S)
    selon le taux d'hospitalisation de chaque colonne."""
    if not simulations_foyers:
        return None, None
    
    nb_sims = len(simulations_foyers)
    sim_ref = simulations_foyers[0]
    est_seir = sim_ref["maladie_meta"]["Modele"] == "SEIR"
    province = sim_ref["province"]
    lits_existants = int(sim_ref["df_synth"]["Cpt Lits"].sum()) if ("df_synth" in sim_ref and "Cpt Lits" in sim_ref["df_synth"].columns) else 0
    max_jour = int(sim_ref["df_long"]["Jour"].max())
    
    paliers_jours = list(range(pas_jours, max_jour + 1, pas_jours))
    if not paliers_jours or paliers_jours[-1] != max_jour:
        paliers_jours.append(max_jour)
    paliers_jours = sorted(list(set(paliers_jours)))
    
    taux_hosp_liste = np.round(np.arange(0.05, 1.01, pas_taux), 2)
    
    # Prétraitement des agrégations journalières par simulation
    sim_aggs = []
    for sim in simulations_foyers:
        df_l = sim["df_long"]
        cols_sum = ["Susceptibles (S)", "Infectés (I)", "Rétablis (R)"]
        if est_seir and "Exposés (E)" in df_l.columns:
            cols_sum.append("Exposés (E)")
        df_g = df_l.groupby("Jour")[cols_sum].sum()
        sim_aggs.append(df_g)
        
    lignes_croisees_moy = []
    lignes_matrice_plate = []
    
    for jour in paliers_jours:
        cellules_jour = {}
        
        for taux in taux_hosp_liste:
            col_nom = f"{int(round(taux * 100))}%"
            gamma_mult = 1.0 + alpha_soins * taux
            ratio = 1.0 / gamma_mult
            j_adv = min(max_jour, max(1, int(round(jour * gamma_mult))))
            
            s_sims, e_sims, i_sims, r_sims, lits_sims = [], [], [], [], []
            
            for df_g in sim_aggs:
                if jour in df_g.index:
                    i_base = df_g.loc[jour, "Infectés (I)"]
                    s_base = df_g.loc[jour, "Susceptibles (S)"]
                    e_base = df_g.loc[jour, "Exposés (E)"] if (est_seir and "Exposés (E)" in df_g.columns) else 0
                    
                    # Récupération de R à l'avancement temporel accéléré par l'hospitalisation
                    r_adv = df_g.loc[j_adv, "Rétablis (R)"] if j_adv in df_g.index else df_g.loc[jour, "Rétablis (R)"]
                    
                    # Ajustement des compartiments
                    i_adj = i_base * ratio
                    r_adj = r_adv
                    e_adj = e_base
                    tot_pop = s_base + i_base + (e_base if est_seir else 0) + df_g.loc[jour, "Rétablis (R)"]
                    s_adj = max(0, tot_pop - i_adj - r_adj - (e_adj if est_seir else 0))
                    
                    s_sims.append(s_adj)
                    if est_seir:
                        e_sims.append(e_adj)
                    i_sims.append(i_adj)
                    r_sims.append(r_adj)
                    lits_sims.append(int(np.round(i_adj * taux)))
                    
            s_moy = int(round(float(np.mean(s_sims)))) if s_sims else 0
            e_moy = int(round(float(np.mean(e_sims)))) if (est_seir and e_sims) else 0
            i_moy = int(round(float(np.mean(i_sims)))) if i_sims else 0
            r_moy = int(round(float(np.mean(r_sims)))) if r_sims else 0
            lits_req_moy = int(round(float(np.mean(lits_sims)))) if lits_sims else 0
            
            if est_seir:
                cell_str = (
                    f"Susceptibles: {s_moy:,}\n"
                    f"Exposés: {e_moy:,}\n"
                    f"Infectés: {i_moy:,}\n"
                    f"Rétablis: {r_moy:,}\n"
                    f"Lits existants: {lits_existants:,}\n"
                    f"Lits requis: {lits_req_moy:,}"
                )
            else:
                cell_str = (
                    f"Susceptibles: {s_moy:,}\n"
                    f"Infectés: {i_moy:,}\n"
                    f"Rétablis: {r_moy:,}\n"
                    f"Lits existants: {lits_existants:,}\n"
                    f"Lits requis: {lits_req_moy:,}"
                )
                
            cellules_jour[col_nom] = cell_str
            
            taux_pct = int(round(taux * 100))
            row_plate = {
                "Province": province,
                "Type": f"Moyenne ({nb_sims} Foyers Aléatoires)",
                "Jour": jour,
                "Taux d'Hospitalisation (%)": f"{taux_pct}%",
                "Taux_Num": taux_pct,
                "Susceptibles (Moyenne)": s_moy,
            }
            if est_seir:
                row_plate["Exposés (Moyenne)"] = e_moy
            row_plate["Infectés (Moyenne)"] = i_moy
            row_plate["Rétablis (Moyenne)"] = r_moy
            row_plate["Lits Existants (Province)"] = lits_existants
            row_plate["Lits Requis (Moyenne)"] = lits_req_moy
            row_plate["Lits Occupés"] = lits_req_moy
            
            lignes_matrice_plate.append(row_plate)
            
        lignes_croisees_moy.append(cellules_jour)
        
    df_croise_moyen = pd.DataFrame(lignes_croisees_moy, index=[f"Jour {j}" for j in paliers_jours])
    df_croise_moyen.index.name = "Paliers de Temps"
    df_sensibilite_plate = pd.DataFrame(lignes_matrice_plate)
    
    return df_croise_moyen, df_sensibilite_plate


def simuler_epidemic_streamlit(engine, df_maladies, nom_province, nom_infra_depart="ALEATOIRE", nom_maladie_saisie="Choléra", duree_jours=100, taux_hospitalisation=None, theta=1e-5, gamma_dist=2.0, seed_epicentre=None, distance_max_interprov_km=0, inclure_interprovincial=False):
    """Effectue la simulation SIR / SEIR spatio-temporelle avec prise en compte optionnelle des infrastructures inter-provinciales limitrophes."""
    
    # 1. Infos Maladie
    filtre_maladie = df_maladies['NomMaladie'].astype(str).str.strip().str.lower() == nom_maladie_saisie.strip().lower()
    df_trouve = df_maladies[filtre_maladie]
    
    if df_trouve.empty:
        return None, f"Maladie '{nom_maladie_saisie}' introuvable dans la base de données."
    
    maladie = df_trouve.iloc[0]
    nom_maladie = str(maladie['NomMaladie']).strip()
    R0_base = float(maladie['Ro'])
    D_base = float(maladie['D'])
    gamma_base = 1.0 / D_base
    beta_base = R0_base * gamma_base
    
    modele_type = str(maladie.get('modele', 'SIR')).strip().upper()
    E_base = float(maladie['E']) if pd.notna(maladie.get('E')) and float(maladie.get('E', 0)) > 0 else 0.0
    sigma_base = (1.0 / E_base) if E_base > 0 else 0.0
    
    if taux_hospitalisation is not None:
        taux_hosp = float(taux_hospitalisation)
        if taux_hosp > 1.0:
            taux_hosp = taux_hosp / 100.0
    else:
        taux_hosp = float(maladie.get('TauxHospitalisation', 0.15)) if pd.notna(maladie.get('TauxHospitalisation')) else 0.15
        if taux_hosp > 1.0:
            taux_hosp = taux_hosp / 100.0

    # 2. Chargement des Zones et Détection des Proximités Inter-Provinciales
    df_all_zones = charger_toutes_zones_infrastructures(engine)
    
    # Filtrage de la province principale
    df_main = df_all_zones[df_all_zones['province'].str.strip().str.lower() == nom_province.strip().lower()].copy().reset_index(drop=True)
    
    if df_main.empty:
        return None, f"Aucune zone de santé avec infrastructure géolocalisée dans la province '{nom_province}'."
    
    liaisons_interprovinciales = []
    if inclure_interprovincial and distance_max_interprov_km > 0:
        # Calcul vectorisé des distances entre toutes les zones de santé de la base
        all_lats = np.radians(df_all_zones['latitude_infra'].values)
        all_lons = np.radians(df_all_zones['longitude_infra'].values)
        dlat = all_lats[:, None] - all_lats[None, :]
        dlon = all_lons[:, None] - all_lons[None, :]
        a_geo = np.sin(dlat / 2.0)**2 + np.cos(all_lats[:, None]) * np.cos(all_lats[None, :]) * np.sin(dlon / 2.0)**2
        dist_all_matrix = np.maximum(6371.0 * (2 * np.arctan2(np.sqrt(np.clip(a_geo, 0, 1)), np.sqrt(np.clip(1 - a_geo, 0, 1)))), 0.0)
        
        all_provinces = df_all_zones['province'].str.strip().values
        nom_prov_clean = nom_province.strip().lower()
        
        # Découverte transitive en cascade des provinces connectées ("et dans les provinces voisines ainsi de suite")
        provs_trouvees = {nom_prov_clean}
        changed = True
        while changed:
            changed = False
            for i, p_src in enumerate(all_provinces):
                if p_src.lower() in provs_trouvees:
                    close_idxs = np.where(dist_all_matrix[i] <= distance_max_interprov_km)[0]
                    for j in close_idxs:
                        p_dst = all_provinces[j]
                        if p_dst.lower() not in provs_trouvees:
                            provs_trouvees.add(p_dst.lower())
                            changed = True
                            
        # Récupération de l'ensemble des zones de santé de toutes les provinces connectées
        df_other = df_all_zones[(df_all_zones['province'].str.strip().str.lower() != nom_prov_clean) & 
                                (df_all_zones['province'].str.strip().str.lower().isin(provs_trouvees))].copy().reset_index(drop=True)
        
        if not df_other.empty:
            df_zones_p = pd.concat([df_main, df_other], ignore_index=True)
            
            # Recensement de toutes les liaisons de proximité inter-provinciales
            K_tot = len(df_zones_p)
            z_lats = np.radians(df_zones_p['latitude_infra'].values)
            z_lons = np.radians(df_zones_p['longitude_infra'].values)
            z_dlat = z_lats[:, None] - z_lats[None, :]
            z_dlon = z_lons[:, None] - z_lons[None, :]
            z_a = np.sin(z_dlat / 2.0)**2 + np.cos(z_lats[:, None]) * np.cos(z_lats[None, :]) * np.sin(z_dlon / 2.0)**2
            z_dist = np.maximum(6371.0 * (2 * np.arctan2(np.sqrt(np.clip(z_a, 0, 1)), np.sqrt(np.clip(1 - z_a, 0, 1)))), 0.0)
            
            liaisons_vues = set()
            for i in range(K_tot):
                for j in range(i + 1, K_tot):
                    prov_i = str(df_zones_p.loc[i, 'province']).strip()
                    prov_j = str(df_zones_p.loc[j, 'province']).strip()
                    if prov_i.lower() != prov_j.lower():
                        d_km = z_dist[i, j]
                        if d_km <= distance_max_interprov_km:
                            za = str(df_zones_p.loc[i, 'nomZone'])
                            zb = str(df_zones_p.loc[j, 'nomZone'])
                            ia = str(df_zones_p.loc[i, 'nom_infra_ref'])
                            ib = str(df_zones_p.loc[j, 'nom_infra_ref'])
                            lata = float(df_zones_p.loc[i, 'latitude_infra'])
                            latb = float(df_zones_p.loc[j, 'latitude_infra'])
                            lona = float(df_zones_p.loc[i, 'longitude_infra'])
                            lonb = float(df_zones_p.loc[j, 'longitude_infra'])
                            
                            cle_l = tuple(sorted([za, zb]))
                            if cle_l not in liaisons_vues:
                                liaisons_vues.add(cle_l)
                                liaisons_interprovinciales.append({
                                    "zone_a": za,
                                    "infra_a": ia,
                                    "prov_a": prov_i,
                                    "lat_a": lata,
                                    "lon_a": lona,
                                    "zone_b": zb,
                                    "infra_b": ib,
                                    "prov_b": prov_j,
                                    "lat_b": latb,
                                    "lon_b": lonb,
                                    "dist_km": round(float(d_km), 1)
                                })
            liaisons_interprovinciales.sort(key=lambda x: x["dist_km"])
        else:
            df_zones_p = df_main.copy()
    else:
        df_zones_p = df_main.copy()

    K_main = len(df_main)
    K = len(df_zones_p)
    N_vec = df_zones_p['population_2026'].values
    M = generer_matrice_mobilite_infrastructures(df_zones_p, theta=theta, gamma_dist=gamma_dist)
    t_total = np.linspace(1, duree_jours, duree_jours)
    est_seir = (modele_type == 'SEIR' and E_base > 0)

    # 3. Calcul du nombre de zones de santé à sélectionner pour l'échantillonnage multi-foyers :
    # Égal à la moitié des zones de la province principale
    nb_foyers = (K_main // 2) + 1 if (K_main % 2 != 0) else (K_main // 2)
    nb_foyers = max(1, min(K_main, nb_foyers))

    # Générateur aléatoire
    if seed_epicentre is not None:
        try:
            rng = np.random.RandomState(int(seed_epicentre))
        except Exception:
            rng = np.random.RandomState()
    else:
        rng = np.random.RandomState()

    est_aleatoire = False
    infra_saisie = str(nom_infra_depart).strip() if nom_infra_depart is not None else ""
    if (not infra_saisie) or infra_saisie.upper() in ["ALEATOIRE", "ALÉATOIRE", "RANDOM", "AUCUNE INFRASTRUCTURE"]:
        est_aleatoire = True

    if est_aleatoire:
        # Tirage aléatoire sans remise parmi les zones de la province principale
        indices_foyers = rng.choice(K_main, size=nb_foyers, replace=False).tolist()
    else:
        # Recherche de l'infrastructure saisie
        saisie_epuree = infra_saisie.lower()
        colonne_nom_infra = trouver_nom_colonne_infra(engine)
        query_flexible = text(f"""
            SELECT 
                i.idZone AS idZone_sante,
                i.{colonne_nom_infra} AS nom_infra_trouve,
                i.latitude,
                i.longitude,
                z.NomZone AS nomZone
            FROM infrastructures i
            JOIN zonesante z ON i.idZone = z.idZone
            WHERE LOWER(i.{colonne_nom_infra}) LIKE :infra
            LIMIT 1
        """)
        with engine.connect() as conn:
            df_dep = pd.read_sql(query_flexible, conn, params={"infra": f"%{saisie_epuree}%"})

        idx_manuel = 0
        if not df_dep.empty:
            id_zone_trouvee = df_dep.iloc[0]['idZone_sante']
            match_idx = df_zones_p[df_zones_p['idZone'] == id_zone_trouvee].index
            if len(match_idx) > 0:
                idx_manuel = match_idx[0]
                df_zones_p.loc[idx_manuel, 'latitude_infra'] = df_dep.iloc[0]['latitude']
                df_zones_p.loc[idx_manuel, 'longitude_infra'] = df_dep.iloc[0]['longitude']
                df_zones_p.loc[idx_manuel, 'nom_infra_ref'] = df_dep.iloc[0]['nom_infra_trouve']
            else:
                idx_manuel = int(rng.randint(0, K_main))
        else:
            idx_manuel = int(rng.randint(0, K_main))

        autres_indices = [i for i in range(K_main) if i != idx_manuel]
        nb_a_tirer = min(nb_foyers - 1, len(autres_indices))
        if nb_a_tirer > 0:
            indices_extra = rng.choice(autres_indices, size=nb_a_tirer, replace=False).tolist()
            indices_foyers = [idx_manuel] + indices_extra
        else:
            indices_foyers = [idx_manuel]

    # 4. Simulation pour chaque foyer sélectionné
    simulations_foyers = []
    for rank, idx_f in enumerate(indices_foyers):
        mode_f = "Manuel" if (not est_aleatoire and rank == 0) else "Aléatoire"
        res_f = resoudre_simulation_seir_zone(
            idx_start=idx_f,
            df_zones_p=df_zones_p,
            N_vec=N_vec,
            M=M,
            t_total=t_total,
            est_seir=est_seir,
            beta_base=beta_base,
            gamma_base=gamma_base,
            sigma_base=sigma_base,
            taux_hosp=taux_hosp,
            nom_maladie=nom_maladie,
            R0_base=R0_base,
            D_base=D_base,
            E_base=E_base,
            nom_province=nom_province,
            mode_selection=mode_f
        )
        simulations_foyers.append(res_f)

    # 5. Calcul du tableau croisé moyen et de la matrice de sensibilité provinciale moyenne
    df_croise_moyen, df_sensibilite_moyenne = generer_analyse_sensibilite_provinciale_moyenne(
        simulations_foyers, pas_jours=10, pas_taux=0.05
    )

    # Simulation principale (foyer 1) utilisée par défaut pour la carte et les courbes individuelles
    resultats = simulations_foyers[0].copy()
    resultats["simulations_foyers"] = simulations_foyers
    resultats["indices_foyers"] = indices_foyers
    resultats["nb_foyers_total"] = len(indices_foyers)
    resultats["total_zones_province"] = K
    resultats["df_croise_moyen"] = df_croise_moyen
    resultats["df_sensibilite_moyenne"] = df_sensibilite_moyenne
    resultats["liaisons_interprovinciales"] = liaisons_interprovinciales
    resultats["distance_interprov_max"] = distance_max_interprov_km if inclure_interprovincial else 0
    resultats["inclure_interprovincial"] = inclure_interprovincial
    resultats["provinces_incluses"] = list(df_zones_p['province'].dropna().unique())
    resultats["nb_zones_principales"] = K_main
    resultats["nb_zones_voisines"] = K - K_main

    df_synth_full = resultats["df_synth"]
    df_long_full = resultats["df_long"]
    province_filtre = df_synth_full["Province"].astype(str).str.strip().str.lower() == nom_province.strip().lower()
    resultats["df_synth_province"] = df_synth_full.loc[province_filtre].copy() if not df_synth_full.empty else df_synth_full.copy()
    if not df_long_full.empty and "Province" in df_long_full.columns:
        resultats["df_prov_daily_province"] = (
            df_long_full.loc[df_long_full["Province"].astype(str).str.strip().str.lower() == nom_province.strip().lower()]
            .groupby("Jour")[["Susceptibles (S)", "Infectés (I)", "Rétablis (R)", "Lits Occupés"]]
            .sum()
            .reset_index()
        )
        if "Exposés (E)" in df_long_full.columns:
            resultats["df_prov_daily_province"]["Exposés (E)"] = (
                df_long_full.loc[df_long_full["Province"].astype(str).str.strip().str.lower() == nom_province.strip().lower()]
                .groupby("Jour")["Exposés (E)"]
                .sum()
                .values
            )
    else:
        resultats["df_prov_daily_province"] = resultats["df_prov_daily"].copy()

    return resultats, None



# 3. MODULE D'ANALYSE DE SENSIBILITÉ MULTIDIMENSIONNELLE

def generer_matrice_sensibilite(sim_data, pas_jours=10, pas_taux=0.05, alpha_soins=0.8):
    df_long = sim_data["df_long"]
    df_synth = sim_data.get("df_synth")
    province = sim_data["province"]
    epicentre = sim_data["infra_depart"]
    est_seir = sim_data["maladie_meta"]["Modele"] == "SEIR"
    lits_existants = int(df_synth["Cpt Lits"].sum()) if (df_synth is not None and "Cpt Lits" in df_synth.columns) else 0
    
    max_jour = int(df_long["Jour"].max())
    
    # 1. Paliers de jours : 10, 20, 30... jusqu'à la durée max
    paliers_jours = list(range(pas_jours, max_jour + 1, pas_jours))
    if not paliers_jours or paliers_jours[-1] != max_jour:
        paliers_jours.append(max_jour)
    paliers_jours = sorted(list(set(paliers_jours)))
    
    # 2. Taux d'hospitalisation de 5% à 100% par pas de 5% (0.05, 0.10, ..., 1.00)
    taux_hosp_liste = np.round(np.arange(0.05, 1.01, pas_taux), 2)
    
    cols_sum = ["Susceptibles (S)", "Infectés (I)", "Rétablis (R)"]
    if est_seir and "Exposés (E)" in df_long.columns:
        cols_sum.append("Exposés (E)")
    df_g = df_long.groupby("Jour")[cols_sum].sum()
    
    lignes_matrice = []
    
    for jour in paliers_jours:
        if jour not in df_g.index:
            continue
            
        i_base = df_g.loc[jour, "Infectés (I)"]
        s_base = df_g.loc[jour, "Susceptibles (S)"]
        e_base = df_g.loc[jour, "Exposés (E)"] if (est_seir and "Exposés (E)" in df_g.columns) else 0
        tot_pop = s_base + i_base + (e_base if est_seir else 0) + df_g.loc[jour, "Rétablis (R)"]
        
        for taux in taux_hosp_liste:
            taux_pct = int(round(taux * 100))
            gamma_mult = 1.0 + alpha_soins * taux
            ratio = 1.0 / gamma_mult
            j_adv = min(max_jour, max(1, int(round(jour * gamma_mult))))
            
            r_adj = int(round(df_g.loc[j_adv, "Rétablis (R)"])) if j_adv in df_g.index else int(round(df_g.loc[jour, "Rétablis (R)"]))
            i_adj = int(round(i_base * ratio))
            e_adj = int(round(e_base)) if est_seir else 0
            s_adj = max(0, int(round(tot_pop - i_adj - r_adj - e_adj)))
            
            lits_requis_totaux = int(np.round(i_adj * taux))
            
            row_data = {
                "Province": province,
                "Infrastructure (Épicentre)": epicentre,
                "Jour": jour,
                "Taux d'Hospitalisation (%)": f"{taux_pct}%",
                "Taux_Num": taux_pct,
                "Susceptibles": s_adj,
            }
            if est_seir:
                row_data["Exposés"] = e_adj
            row_data["Infectés"] = i_adj
            row_data["Rétablis"] = r_adj
            row_data["Lits Existants"] = lits_existants
            row_data["Lits Requis"] = lits_requis_totaux
            row_data["Lits Occupés"] = lits_requis_totaux
            
            lignes_matrice.append(row_data)
            
    df_sensibilite = pd.DataFrame(lignes_matrice)
    return df_sensibilite


def generer_tableau_croise_seir(sim_data, pas_jours=10, pas_taux=0.05, format_cellule="seir", alpha_soins=0.8):
    df_long = sim_data["df_long"]
    df_synth = sim_data.get("df_synth")
    est_seir = sim_data["maladie_meta"]["Modele"] == "SEIR"
    lits_existants = int(df_synth["Cpt Lits"].sum()) if (df_synth is not None and "Cpt Lits" in df_synth.columns) else 0
    max_jour = int(df_long["Jour"].max())
    
    paliers_jours = list(range(pas_jours, max_jour + 1, pas_jours))
    if not paliers_jours or paliers_jours[-1] != max_jour:
        paliers_jours.append(max_jour)
    paliers_jours = sorted(list(set(paliers_jours)))
    
    taux_hosp_liste = np.round(np.arange(0.05, 1.01, pas_taux), 2)
    
    cols_sum = ["Susceptibles (S)", "Infectés (I)", "Rétablis (R)"]
    if est_seir and "Exposés (E)" in df_long.columns:
        cols_sum.append("Exposés (E)")
    df_g = df_long.groupby("Jour")[cols_sum].sum()
    
    lignes_croisees = []
    
    for jour in paliers_jours:
        if jour not in df_g.index:
            continue
            
        i_base = df_g.loc[jour, "Infectés (I)"]
        s_base = df_g.loc[jour, "Susceptibles (S)"]
        e_base = df_g.loc[jour, "Exposés (E)"] if (est_seir and "Exposés (E)" in df_g.columns) else 0
        tot_pop = s_base + i_base + (e_base if est_seir else 0) + df_g.loc[jour, "Rétablis (R)"]
        
        cellules_jour = {}
        for taux in taux_hosp_liste:
            col_nom = f"{int(round(taux * 100))}%"
            gamma_mult = 1.0 + alpha_soins * taux
            ratio = 1.0 / gamma_mult
            j_adv = min(max_jour, max(1, int(round(jour * gamma_mult))))
            
            r_val = int(round(df_g.loc[j_adv, "Rétablis (R)"])) if j_adv in df_g.index else int(round(df_g.loc[jour, "Rétablis (R)"]))
            i_val = int(round(i_base * ratio))
            e_val = int(round(e_base)) if est_seir else 0
            s_val = max(0, int(round(tot_pop - i_val - r_val - e_val)))
            lits_req = int(np.round(i_val * taux))
            
            if format_cellule in ("seir", "seir_lits"):
                if est_seir:
                    cell_str = (
                        f"Susceptibles: {s_val:,}\n"
                        f"Exposés: {e_val:,}\n"
                        f"Infectés: {i_val:,}\n"
                        f"Rétablis: {r_val:,}\n"
                        f"Lits existants: {lits_existants:,}\n"
                        f"Lits requis: {lits_req:,}"
                    )
                else:
                    cell_str = (
                        f"Susceptibles: {s_val:,}\n"
                        f"Infectés: {i_val:,}\n"
                        f"Rétablis: {r_val:,}\n"
                        f"Lits existants: {lits_existants:,}\n"
                        f"Lits requis: {lits_req:,}"
                    )
            elif format_cellule == "dict":
                d_cell = {
                    "Susceptibles": s_val,
                    "Infectés": i_val,
                    "Rétablis": r_val,
                    "Lits existants": lits_existants,
                    "Lits requis": lits_req
                }
                if est_seir:
                    d_cell["Exposés"] = e_val
                cell_str = str(d_cell)
            elif format_cellule == "lits_seuls":
                cell_str = f"Lits existants: {lits_existants:,}\nLits requis: {lits_req:,}"
            elif format_cellule == "infectes_seuls":
                cell_str = i_val
            elif format_cellule == "susceptibles_seuls":
                cell_str = s_val
            elif format_cellule == "exposes_seuls":
                cell_str = e_val
            elif format_cellule == "retablis_seuls":
                cell_str = r_val
            else:
                cell_str = f"S:{s_val:,}\nE:{e_val:,}\nI:{i_val:,}\nR:{r_val:,}\nLits dispo:{lits_existants:,}\nLits req:{lits_req:,}"
                
            cellules_jour[col_nom] = cell_str
            
        lignes_croisees.append(cellules_jour)
        
    df_croise = pd.DataFrame(lignes_croisees, index=[f"Jour {j}" for j in paliers_jours])
    df_croise.index.name = "Paliers de Temps"
    return df_croise


def creer_graphique_sensibilite_provinciale(df_sensibilite, taux_pct, nom_province, nom_maladie, modele):
    """Crée le graphique temporel de la moyenne provinciale pour un taux donné."""
    if not HAS_PLOTLY or df_sensibilite is None or df_sensibilite.empty:
        return None

    df_taux = df_sensibilite[df_sensibilite["Taux_Num"] == taux_pct].sort_values("Jour")
    if df_taux.empty:
        return None

    series = [
        ("Susceptibles", "Susceptibles (Moyenne)"),
        ("Infectés", "Infectés (Moyenne)"),
        ("Rétablis", "Rétablis (Moyenne)"),
    ]
    if modele == "SEIR" and "Exposés (Moyenne)" in df_taux.columns:
        series.insert(1, ("Exposés", "Exposés (Moyenne)"))

    couleurs = {
        "Susceptibles": "#0284c7",
        "Exposés": "#f59e0b",
        "Infectés": "#dc2626",
        "Rétablis": "#059669",
    }
    fig = go.Figure()
    for nom_serie, colonne in series:
        valeurs = df_taux[colonne].astype(float).tolist()
        effectif_max = max(
            1.0,
            max(float(df_taux[colonne_serie].max()) for _, colonne_serie in series)
        )
        marqueurs = [
            8 + 20 * np.sqrt(max(0, valeur) / effectif_max)
            for valeur in valeurs
        ]
        fig.add_trace(go.Scatter(
            x=df_taux["Jour"].tolist(),
            y=[nom_serie] * len(df_taux),
            mode="lines+markers",
            name=nom_serie,
            line=dict(color=couleurs[nom_serie], width=2),
            marker=dict(size=marqueurs, color=couleurs[nom_serie]),
            customdata=valeurs,
            hovertemplate="Jour %{x}<br>Type : <b>%{y}</b><br>Effectif : <b>%{customdata:,.0f}</b><extra></extra>"
        ))

    fig.update_layout(
        title=f"Moyenne provinciale - {nom_maladie} - Taux d'hospitalisation : {taux_pct}%",
        xaxis=dict(title="Jour de simulation", showgrid=False, dtick=5),
        yaxis=dict(
            title="Type d'individus",
            type="category",
            categoryorder="array",
            categoryarray=[nom_serie for nom_serie, _ in series],
            autorange="reversed"
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=500,
        margin=dict(l=52, r=24, t=76, b=64),
        font=dict(family="Arial, sans-serif", size=12, color="#334155"),
        legend=dict(title="Types d'individus", orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="#0f172a", font_size=12),
        annotations=[dict(
            x=0, y=-0.18, xref="paper", yref="paper", showarrow=False,
            text="Légende : couleur = type d'individus | taille du point = effectif",
            font=dict(size=11, color="#64748b"), align="left"
        )],
    )
    return fig


def _generer_images_sensibilite_cartes(df_sensibilite, nom_province, nom_maladie, modele, dpi=180):
    """Génère une planche PNG avec une carte par variable épidémiologique."""
    if not HAS_MATPLOTLIB or df_sensibilite is None or df_sensibilite.empty:
        return None

    series = [
        ("Susceptibles", "Susceptibles (Moyenne)"),
        ("Infectés", "Infectés (Moyenne)"),
        ("Rétablis", "Rétablis (Moyenne)"),
    ]
    if modele == "SEIR" and "Exposés (Moyenne)" in df_sensibilite.columns:
        series.insert(1, ("Exposés", "Exposés (Moyenne)"))

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as fichier_zip:
        fig, axes = plt.subplots(2, 2, figsize=(16, 11), dpi=dpi, squeeze=False)
        axes_plats = axes.ravel()
        for axe, (nom_serie, colonne) in zip(axes_plats, series):
            tableau = df_sensibilite.pivot_table(
                index="Taux_Num", columns="Jour", values=colonne, aggfunc="mean"
            ).sort_index()
            image = axe.imshow(
                tableau.to_numpy(dtype=float), aspect="auto", origin="lower",
                interpolation="nearest", cmap="YlOrRd",
                extent=[
                    float(tableau.columns.min()), float(tableau.columns.max()),
                    float(tableau.index.min()), float(tableau.index.max())
                ]
            )
            axe.set_title(nom_serie, fontweight="bold")
            axe.set_xlabel("Jour de simulation")
            axe.set_ylabel("Taux d'hospitalisation (%)")
            axe.set_yticks(tableau.index.tolist())
            axe.set_xticks(tableau.columns.tolist()[::max(1, len(tableau.columns) // 8)])
            fig.colorbar(image, ax=axe, shrink=0.82, label="Effectif")

        for axe in axes_plats[len(series):]:
            axe.set_visible(False)
        fig.suptitle(
            f"Analyse de sensibilité - Moyenne provinciale\n"
            f"{nom_maladie} | {nom_province} | Modèle {modele}",
            fontsize=15, fontweight="bold"
        )
        fig.text(
            0.5, 0.01,
            "Légende : axe X = jours | axe Y = taux d'hospitalisation | couleur = effectif",
            ha="center", fontsize=10, color="#64748b"
        )
        fig.tight_layout(rect=(0, 0.03, 1, 0.94))
        image = io.BytesIO()
        fig.savefig(image, format="png", dpi=dpi, bbox_inches="tight")
        image.seek(0)
        fichier_zip.writestr("sensibilite_moyenne_variables_S_I_E_R.png", image.read())
        plt.close(fig)
    archive.seek(0)
    return archive


def generer_images_sensibilite_provinciale(df_sensibilite, nom_province, nom_maladie, modele, dpi=180):
    """Génère un ZIP de PNG, avec six taux d'hospitalisation par image."""
    return _generer_images_sensibilite_cartes(df_sensibilite, nom_province, nom_maladie, modele, dpi)
    if not HAS_MATPLOTLIB or df_sensibilite is None or df_sensibilite.empty:
        return None

    series = [
        ("Susceptibles", "Susceptibles (Moyenne)", "#0284c7"),
        ("Infectés", "Infectés (Moyenne)", "#dc2626"),
        ("Rétablis", "Rétablis (Moyenne)", "#059669"),
    ]
    if modele == "SEIR" and "Exposés (Moyenne)" in df_sensibilite.columns:
        series.insert(1, ("Exposés", "Exposés (Moyenne)", "#f59e0b"))

    taux_disponibles = sorted(df_sensibilite["Taux_Num"].dropna().astype(int).unique().tolist())
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as fichier_zip:
        for numero_page, debut in enumerate(range(0, len(taux_disponibles), 6), start=1):
            taux_page = taux_disponibles[debut:debut + 6]
            fig, axes = plt.subplots(2, 3, figsize=(16, 9), dpi=dpi, squeeze=False)
            axes_plats = axes.ravel()

            for index_graphique, (axe, taux_pct) in enumerate(zip(axes_plats, taux_page)):
                df_taux = df_sensibilite[
                    df_sensibilite["Taux_Num"].astype(int) == taux_pct
                ].sort_values("Jour")
                effectif_max = max(
                    1.0,
                    max(float(df_taux[colonne].max()) for _, colonne, _ in series)
                )
                for nom_serie, colonne, couleur in series:
                    valeurs = df_taux[colonne].astype(float).to_numpy()
                    tailles = [
                        18 + 90 * np.sqrt(max(0, valeur) / effectif_max)
                        for valeur in valeurs
                    ]
                    axe.plot(
                        df_taux["Jour"], [nom_serie] * len(df_taux),
                        marker="o", markersize=3, linewidth=1.5,
                        color=couleur, label=nom_serie
                    )
                    axe.scatter(df_taux["Jour"], [nom_serie] * len(df_taux), s=tailles, color=couleur, alpha=0.75)
                axe.set_title(f"Taux d'hospitalisation : {taux_pct}%", fontweight="bold")
                axe.set_xlabel("Jour de simulation")
                axe.set_ylabel("Type d'individus")
                axe.set_yticks([nom_serie for nom_serie, _, _ in series])
                axe.set_yticklabels([nom_serie for nom_serie, _, _ in series])
                axe.grid(True, linestyle="--", alpha=0.3)
                axe.legend(loc="best", fontsize=8, frameon=True)

            for axe in axes_plats[len(taux_page):]:
                axe.set_visible(False)

            fig.suptitle(
                f"Analyse de sensibilité - Moyenne provinciale\n"
                f"{nom_maladie} | {nom_province} | Modèle {modele}",
                fontsize=15, fontweight="bold"
            )
            fig.text(
                0.5, 0.01,
                "Légende : couleur = type d'individus | taille du point = effectif",
                ha="center", fontsize=10, color="#64748b"
            )
            fig.tight_layout(rect=(0, 0.01, 1, 0.94))
            image = io.BytesIO()
            fig.savefig(image, format="png", dpi=dpi, bbox_inches="tight")
            image.seek(0)
            fichier_zip.writestr(
                f"sensibilite_moyenne_page_{numero_page}_taux_{taux_page[0]}_{taux_page[-1]}_pourcent.png",
                image.read()
            )
            plt.close(fig)

    archive.seek(0)
    return archive


def _generer_images_sensibilite_lits_cartes(df_sensibilite, nom_province, nom_maladie, dpi=180):
    """Génère une planche PNG avec une carte par type de lits."""
    colonnes_requises = {
        "Jour", "Taux_Num", "Lits Existants (Province)", "Lits Requis (Moyenne)"
    }
    if not HAS_MATPLOTLIB or df_sensibilite is None or df_sensibilite.empty:
        return None
    if not colonnes_requises.issubset(df_sensibilite.columns):
        return None

    series = [
        ("Lits existants", "Lits Existants (Province)", "Blues"),
        ("Lits requis", "Lits Requis (Moyenne)", "Reds"),
    ]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as fichier_zip:
        fig, axes = plt.subplots(1, 2, figsize=(16, 6.5), dpi=dpi, squeeze=False)
        for axe, (nom_serie, colonne, cmap) in zip(axes.ravel(), series):
            tableau = df_sensibilite.pivot_table(
                index="Taux_Num", columns="Jour", values=colonne, aggfunc="mean"
            ).sort_index()
            image = axe.imshow(
                tableau.to_numpy(dtype=float), aspect="auto", origin="lower",
                interpolation="nearest", cmap=cmap,
                extent=[
                    float(tableau.columns.min()), float(tableau.columns.max()),
                    float(tableau.index.min()), float(tableau.index.max())
                ]
            )
            axe.set_title(nom_serie, fontweight="bold")
            axe.set_xlabel("Jour de simulation")
            axe.set_ylabel("Taux d'hospitalisation (%)")
            axe.set_yticks(tableau.index.tolist())
            axe.set_xticks(tableau.columns.tolist()[::max(1, len(tableau.columns) // 8)])
            fig.colorbar(image, ax=axe, shrink=0.82, label="Nombre de lits")

        fig.suptitle(
            f"Analyse de sensibilité des lits - Moyenne provinciale\n"
            f"{nom_maladie} | {nom_province}",
            fontsize=15, fontweight="bold"
        )
        fig.text(
            0.5, 0.01,
            "Légende : axe X = jours | axe Y = taux d'hospitalisation | bleu = existants | rouge = requis",
            ha="center", fontsize=10, color="#64748b"
        )
        fig.tight_layout(rect=(0, 0.03, 1, 0.94))
        image = io.BytesIO()
        fig.savefig(image, format="png", dpi=dpi, bbox_inches="tight")
        image.seek(0)
        fichier_zip.writestr("sensibilite_lits_existants_requis.png", image.read())
        plt.close(fig)
    archive.seek(0)
    return archive


def generer_images_sensibilite_lits(df_sensibilite, nom_province, nom_maladie, dpi=180):
    """Génère un ZIP de PNG, avec six graphiques de lits par image."""
    return _generer_images_sensibilite_lits_cartes(df_sensibilite, nom_province, nom_maladie, dpi)
    colonnes_requises = {
        "Jour", "Taux_Num", "Lits Existants (Province)", "Lits Requis (Moyenne)"
    }
    if not HAS_MATPLOTLIB or df_sensibilite is None or df_sensibilite.empty:
        return None
    if not colonnes_requises.issubset(df_sensibilite.columns):
        return None

    series = [
        ("Lits existants", "Lits Existants (Province)", "#2563eb"),
        ("Lits requis", "Lits Requis (Moyenne)", "#e11d48"),
    ]
    taux_disponibles = sorted(df_sensibilite["Taux_Num"].dropna().astype(int).unique().tolist())
    archive = io.BytesIO()

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as fichier_zip:
        for numero_page, debut in enumerate(range(0, len(taux_disponibles), 6), start=1):
            taux_page = taux_disponibles[debut:debut + 6]
            fig, axes = plt.subplots(2, 3, figsize=(16, 9), dpi=dpi, squeeze=False)
            axes_plats = axes.ravel()

            for axe, taux_pct in zip(axes_plats, taux_page):
                df_taux = df_sensibilite[
                    df_sensibilite["Taux_Num"].astype(int) == taux_pct
                ].sort_values("Jour")
                for nom_serie, colonne, couleur in series:
                    axe.plot(
                        df_taux["Jour"], [nom_serie] * len(df_taux),
                        marker="o", markersize=3, linewidth=1.8,
                        color=couleur, label=nom_serie
                    )
                axe.set_title(f"Taux d'hospitalisation : {taux_pct}%", fontweight="bold")
                axe.set_xlabel("Jour de simulation")
                axe.set_ylabel("Type de lits")
                axe.set_yticks([nom_serie for nom_serie, _, _ in series])
                axe.set_yticklabels([nom_serie for nom_serie, _, _ in series])
                axe.grid(True, linestyle="--", alpha=0.3)
                axe.legend(loc="best", fontsize=8, frameon=True)

            for axe in axes_plats[len(taux_page):]:
                axe.set_visible(False)

            fig.suptitle(
                f"Analyse de sensibilité des lits - Moyenne provinciale\n"
                f"{nom_maladie} | {nom_province}",
                fontsize=15, fontweight="bold"
            )
            fig.text(
                0.5, 0.01,
                "Légende : bleu = lits existants | rouge = lits requis",
                ha="center", fontsize=10, color="#64748b"
            )
            fig.tight_layout(rect=(0, 0.01, 1, 0.94))
            image = io.BytesIO()
            fig.savefig(image, format="png", dpi=dpi, bbox_inches="tight")
            image.seek(0)
            fichier_zip.writestr(
                f"sensibilite_lits_page_{numero_page}_taux_{taux_page[0]}_{taux_page[-1]}_pourcent.png",
                image.read()
            )
            plt.close(fig)

    archive.seek(0)
    return archive


def generer_html_tableau_croise(df_croise, sim_data, titre_foyer="Paramètres Globaux de la Simulation", info_foyer=None):
    meta = sim_data["maladie_meta"]
    province = sim_data["province"]
    infra = sim_data["infra_depart"]
    zone = sim_data.get("zone_depart", "")
    max_duree_sim = int(sim_data["df_long"]["Jour"].max())
    nb_foyers = sim_data.get("nb_foyers_total", 1)
    total_zones = sim_data.get("total_zones_province", len(sim_data["df_synth"]))
    
    total_cols = len(df_croise.columns) + 1
    
    if info_foyer:
        foyer_html_line = f"<div><b style=\"color: var(--card-text, #0f172a);\">Foyer affiché :</b> {info_foyer}</div>"
    else:
        foyer_html_line = f"<div><b style=\"color: var(--card-text, #0f172a);\">Zone de santé (Infrastructure) :</b> <b>{zone}</b> (<i>{infra}</i>)</div>"
        
    echantillon_line = f"<div><b style=\"color: var(--card-text, #0f172a);\">Échantillonnage multi-foyers :</b> <b>{nb_foyers}</b> zones de santé tirées aléatoirement sur {total_zones} zones ({int(round(nb_foyers/max(1, total_zones)*100))}% de la province)</div>" if nb_foyers > 1 else ""
    
    html = ['<div style="overflow-x: auto; max-height: 680px; border-radius: 10px; border: 1px solid var(--card-border, #cbd5e1); box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin: 8px 0 16px 0; background: var(--card-bg, #ffffff);">']
    html.append('<table style="width: 100%; border-collapse: collapse; font-size: 0.82rem; text-align: left; background: var(--card-bg, #ffffff); color: var(--card-text, #0f172a);">')
    
    # THEAD
    html.append('<thead style="background: var(--card-bg, #ffffff);">')
    
    # 1. EN-TÊTE DES PARAMÈTRES GLOBAUX INTÉGRÉ AU TABLEAU (FOND UNIFORME)
    html.append(f'''
    <tr style="background: var(--card-bg, #ffffff); color: var(--card-text, #0f172a);">
        <th colspan="{total_cols}" style="padding: 14px 18px; border: 1px solid var(--card-border, #cbd5e1); border-bottom: 2px solid var(--card-border, #cbd5e1); text-align: left; font-weight: normal; background: var(--card-bg, #ffffff);">
            <div style="font-size: 0.95rem; font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; color: var(--card-text, #0f172a);">
                <span>{titre_foyer}</span>
                <span style="background: var(--card-bg, #ffffff); color: var(--card-text, #334155); border: 1px solid var(--card-border, #cbd5e1); font-size: 0.78rem; padding: 2px 10px; border-radius: 6px; font-weight: 600;">Modèle {meta['Modele']}</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 5px; font-size: 0.85rem; line-height: 1.5; color: var(--card-text, #334155); padding-top: 2px;">
                <div><b style="color: var(--card-text, #0f172a);">Période :</b> min = 0 - max = {max_duree_sim} jours</div>
                <div><b style="color: var(--card-text, #0f172a);">Maladie :</b> {meta['Nom']}</div>
                <div><b style="color: var(--card-text, #0f172a);">Province :</b> {province}</div>
                {echantillon_line}
                {foyer_html_line}
            </div>
        </th>
    </tr>
    ''')
    
    # 2. LIGNE DES EN-TÊTES DE COLONNES (Paliers de Temps & Taux d'Hospitalisation)
    html.append('<tr style="background: var(--card-bg, #ffffff); color: var(--card-text, #0f172a); position: sticky; top: 0; z-index: 5;">')
    html.append('<th style="padding: 10px 14px; border: 1px solid var(--card-border, #cbd5e1); white-space: nowrap; font-weight: 700; background: var(--card-bg, #ffffff); color: var(--card-text, #0f172a);">Paliers de Temps</th>')
    for col in df_croise.columns:
        html.append(f'<th style="padding: 10px 12px; border: 1px solid var(--card-border, #cbd5e1); text-align: center; white-space: nowrap; font-weight: 600; background: var(--card-bg, #ffffff); color: var(--card-text, #0f172a);">{col}</th>')
    html.append('</tr>')
    
    html.append('</thead><tbody style="background: var(--card-bg, #ffffff);">')
    
    # TBODY : Cellules avec éléments empilés verticalement
    for row_idx, row in df_croise.iterrows():
        html.append('<tr style="border-bottom: 1px solid var(--card-border, #e2e8f0); background: var(--card-bg, #ffffff);">')
        html.append(f'<td style="padding: 10px 14px; font-weight: 700; background: var(--card-bg, #ffffff); border: 1px solid var(--card-border, #e2e8f0); white-space: nowrap; vertical-align: middle; color: var(--card-text, #0f172a);">{row_idx}</td>')
        for col in df_croise.columns:
            cell_text = str(row[col]).replace('\n', '<br>')
            html.append(f'<td style="padding: 8px 12px; border: 1px solid var(--card-border, #e2e8f0); line-height: 1.45; vertical-align: top; white-space: nowrap; font-family: monospace; font-size: 0.78rem; background: var(--card-bg, #ffffff); color: var(--card-text, #1e293b);">{cell_text}</td>')
        html.append('</tr>')
        
    html.append('</tbody></table></div>')
    return "".join(html)


def calculer_indicateurs_optimisation_hospitalisation(sim_source, sim_foyers=None, is_moyenne=True, taux_actuel=0.05):
    """
    Calcule pour tous les taux d'hospitalisation (5% à 100% par pas de 5%) :
    - Le nombre de jours de saturation (Lits Requis > Lits Existants)
    - Le pourcentage de la durée épidémique en saturation
    - Le pic de déficit en lits
    - Le premier et le dernier jour de rupture
    - Le taux optimal maximal soutenable garantissant 0 jour de dépassement capacitaire
    - L'estimation des renforts en lits nécessaires au taux actuel
    """
    df_synth = sim_source.get("df_synth")
    lits_existants = int(df_synth["Cpt Lits"].sum()) if (df_synth is not None and "Cpt Lits" in df_synth.columns) else 0

    if is_moyenne and sim_foyers:
        sim_daily_I = []
        for sim in sim_foyers:
            d_j = sim["df_long"].groupby("Jour")["Infectés (I)"].sum()
            sim_daily_I.append(d_j)
        df_daily_all = pd.concat(sim_daily_I, axis=1)
        serie_I = df_daily_all.mean(axis=1)
    else:
        serie_I = sim_source["df_long"].groupby("Jour")["Infectés (I)"].sum()

    I_max = float(serie_I.max()) if not serie_I.empty else 0.0
    idx_pic = int(serie_I.idxmax()) if not serie_I.empty else 1
    duree_sim = int(serie_I.index.max()) if not serie_I.empty else 100

    # Taux optimal maximal sans aucun jour de saturation (0 jour de dépassement)
    taux_optimal_pct = min(100.0, (lits_existants / I_max) * 100.0) if I_max > 0 else 100.0
    taux_optimal_pct = round(taux_optimal_pct, 1)

    taux_hosp_liste = np.round(np.arange(0.05, 1.01, 0.05), 2)
    lignes_opt = []

    for taux in taux_hosp_liste:
        taux_pct = int(round(taux * 100))
        lits_req_serie = np.round(serie_I * taux)
        deficit_serie = np.maximum(0, lits_req_serie - lits_existants)
        sature_serie = lits_req_serie > lits_existants
        
        jours_sat = int(np.sum(sature_serie))
        pct_sat = round((jours_sat / max(1, duree_sim)) * 100, 1)
        def_max = int(np.max(deficit_serie))
        lits_pic = int(round(I_max * taux))
        
        jours_idx = serie_I.index[sature_serie]
        t_debut = f"Jour {int(jours_idx[0])}" if len(jours_idx) > 0 else "-"
        t_fin = f"Jour {int(jours_idx[-1])}" if len(jours_idx) > 0 else "-"
        periode = f"{t_debut} → {t_fin}" if len(jours_idx) > 0 else "Aucune (0j)"
        
        if jours_sat == 0:
            statut = "Soutenable (0j)"
        elif pct_sat <= 20:
            statut = "Tension Modérée"
        else:
            statut = "Saturation Critique"
            
        lignes_opt.append({
            "Taux d'Hospitalisation (%)": f"{taux_pct}%",
            "Taux_Num": taux_pct,
            "Taux_Val": taux,
            "Jours de Saturation": jours_sat,
            "% Durée Saturée": f"{pct_sat}%",
            "Déficit Max (Lits)": def_max,
            "Lits Requis au Pic": lits_pic,
            "Période de Saturation": periode,
            "Jour Début": t_debut,
            "Jour Fin": t_fin,
            "Statut Capacitaire": statut
        })

    df_opt = pd.DataFrame(lignes_opt)

    # Calcul spécifique pour le taux actuel de la simulation
    taux_actuel_float = float(taux_actuel) if taux_actuel <= 1.0 else float(taux_actuel) / 100.0
    taux_actuel_pct = int(round(taux_actuel_float * 100))
    lits_req_actuel_serie = np.round(serie_I * taux_actuel_float)
    deficit_actuel_serie = np.maximum(0, lits_req_actuel_serie - lits_existants)
    sature_actuel_serie = lits_req_actuel_serie > lits_existants
    jours_sat_actuel = int(np.sum(sature_actuel_serie))
    def_max_actuel = int(np.max(deficit_actuel_serie))
    lits_pic_actuel = int(round(I_max * taux_actuel_float))
    lits_renfort_necessaires = max(0, lits_pic_actuel - lits_existants)

    return {
        "df_opt": df_opt,
        "taux_optimal_pct": taux_optimal_pct,
        "taux_optimal_acceptable_pct": taux_optimal_pct,
        "taux_actuel_pct": taux_actuel_pct,
        "jours_sat_actuel": jours_sat_actuel,
        "def_max_actuel": def_max_actuel,
        "lits_pic_actuel": lits_pic_actuel,
        "lits_renfort_necessaires": lits_renfort_necessaires,
        "lits_existants": lits_existants,
        "I_max": int(round(I_max)),
        "jour_pic": idx_pic,
        "duree_sim": duree_sim,
        "serie_I": serie_I
    }


def creer_graphique_optimisation_hospitalisation(res_opt):
    """Génère un graphique Plotly double axe illustrant l'impact du taux d'hospitalisation sur les jours de saturation et le déficit de lits."""
    if not HAS_PLOTLY:
        return None
        
    df_opt = res_opt["df_opt"]
    taux_opt_val = res_opt["taux_optimal_pct"]
    taux_act_val = res_opt["taux_actuel_pct"]
    
    fig = go.Figure()
    
    # 1. Barres : Jours de saturation capacitaire
    fig.add_trace(go.Bar(
        x=df_opt["Taux_Num"],
        y=df_opt["Jours de Saturation"],
        name="Jours de Saturation (Déficit > 0)",
        marker_color="#ef4444",
        opacity=0.75,
        yaxis="y1",
        hovertemplate="Taux: <b>%{x}%</b><br>Jours saturés: <b>%{y} jours</b><extra></extra>"
    ))
    
    # 2. Ligne : Déficit maximal de lits au pic
    fig.add_trace(go.Scatter(
        x=df_opt["Taux_Num"],
        y=df_opt["Déficit Max (Lits)"],
        name="Pic de Déficit de Lits (Manquants)",
        mode="lines+markers",
        line=dict(color="#f59e0b", width=3),
        marker=dict(size=6, color="#d97706"),
        yaxis="y2",
        hovertemplate="Taux: <b>%{x}%</b><br>Déficit max: <b>%{y:,} lits</b><extra></extra>"
    ))
    
    # 3. Ligne de repère : Taux optimal (0 jour de saturation)
    if 0 < taux_opt_val <= 100:
        fig.add_vline(
            x=taux_opt_val,
            line_width=2.5,
            line_dash="dash",
            line_color="#10b981",
            annotation_text=f"Optimum: {taux_opt_val}% (0j saturation)",
            annotation_position="top left",
            annotation_font=dict(color="#10b981", size=11)
        )
        
    # 4. Ligne de repère : Taux actuel
    fig.add_vline(
        x=taux_act_val,
        line_width=2,
        line_dash="dot",
        line_color="#0284c7",
        annotation_text=f"Taux Actuel: {taux_act_val}%",
        annotation_position="bottom right",
        annotation_font=dict(color="#0284c7", size=11)
    )
    
    # Layout double axe Y
    fig.update_layout(
        title="<b>Arbitrage & Optimisation : Jours de Saturation vs Déficit de Lits</b>",
        xaxis=dict(
            title="Taux d'Hospitalisation des Infectés (%)",
            tickmode="linear",
            tick0=5,
            dtick=10,
            gridcolor="rgba(203, 213, 225, 0.3)"
        ),
        yaxis=dict(
            title=dict(text="Jours de Saturation Hospitalière (Jours)", font=dict(color="#ef4444")),
            tickfont=dict(color="#ef4444"),
            gridcolor="rgba(203, 213, 225, 0.3)"
        ),
        yaxis2=dict(
            title=dict(text="Déficit Maximal en Lits au Pic", font=dict(color="#f59e0b")),
            tickfont=dict(color="#f59e0b"),
            overlaying="y",
            side="right",
            showgrid=False
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=430,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
        hovermode="x unified"
    )
    
    return fig


def creer_graphique_optimisation_hospitalisation(res_opt):
    """Génère un graphique Plotly double axe illustrant l'impact du taux d'hospitalisation sur les jours de saturation et le déficit de lits."""
    if not HAS_PLOTLY:
        return None
        
    df_opt = res_opt["df_opt"]
    taux_opt_val = res_opt["taux_optimal_pct"]
    taux_act_val = res_opt["taux_actuel_pct"]
    
    fig = go.Figure()
    
    # 1. Barres : Jours de saturation capacitaire
    fig.add_trace(go.Bar(
        x=df_opt["Taux_Num"],
        y=df_opt["Jours de Saturation"],
        name="Jours de Saturation (Déficit > 0)",
        marker_color="#ef4444",
        opacity=0.75,
        yaxis="y1",
        hovertemplate="Taux: <b>%{x}%</b><br>Jours saturés: <b>%{y} jours</b><extra></extra>"
    ))
    
    # 2. Ligne : Déficit maximal de lits au pic
    fig.add_trace(go.Scatter(
        x=df_opt["Taux_Num"],
        y=df_opt["Déficit Max (Lits)"],
        name="Pic de Déficit de Lits (Manquants)",
        mode="lines+markers",
        line=dict(color="#f59e0b", width=3),
        marker=dict(size=6, color="#d97706"),
        yaxis="y2",
        hovertemplate="Taux: <b>%{x}%</b><br>Déficit max: <b>%{y:,} lits</b><extra></extra>"
    ))
    
    # 3. Ligne de repère : Taux optimal (0 jour de saturation)
    if 0 < taux_opt_val <= 100:
        fig.add_vline(
            x=taux_opt_val,
            line_width=2.5,
            line_dash="dash",
            line_color="#10b981",
            annotation_text=f"Optimum: {taux_opt_val}% (0j saturation)",
            annotation_position="top left",
            annotation_font=dict(color="#10b981", size=11)
        )
        
    # 4. Ligne de repère : Taux actuel
    fig.add_vline(
        x=taux_act_val,
        line_width=2,
        line_dash="dot",
        line_color="#0284c7",
        annotation_text=f"Taux Actuel: {taux_act_val}%",
        annotation_position="bottom right",
        annotation_font=dict(color="#0284c7", size=11)
    )
    
    # Layout double axe Y
    fig.update_layout(
        title="<b>Arbitrage & Optimisation : Jours de Saturation vs Déficit de Lits</b>",
        xaxis=dict(
            title="Taux d'Hospitalisation des Infectés (%)",
            tickmode="linear",
            tick0=5,
            dtick=10,
            gridcolor="rgba(203, 213, 225, 0.3)"
        ),
        yaxis=dict(
            title=dict(text="Jours de Saturation Hospitalière (Jours)", font=dict(color="#ef4444")),
            tickfont=dict(color="#ef4444"),
            gridcolor="rgba(203, 213, 225, 0.3)"
        ),
        yaxis2=dict(
            title=dict(text="Déficit Maximal en Lits au Pic", font=dict(color="#f59e0b")),
            tickfont=dict(color="#f59e0b"),
            overlaying="y",
            side="right",
            showgrid=False
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=430,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
        hovermode="x unified"
    )
    
    return fig


# ==============================================================================
# 3. BIS - MODULE DE VISUALISATION ET D'EXPORTATION HAUTE DÉFINITION (MATPLOTLIB)
# ==============================================================================

def formateur_milliers_mpl(x, pos):
    """Formate les grands nombres en k et M pour les axes Matplotlib."""
    if abs(x) >= 1e6:
        return f"{x*1e-6:.1f} M"
    elif abs(x) >= 1e3:
        return f"{x*1e-3:.0f} k"
    else:
        return f"{int(x)}"

def creer_figure_matplotlib_dynamique_globale(df_prov_daily, nom_province, nom_maladie, est_seir, r0=None, figsize=(10, 5.2), dpi=300):
    """Génère une figure Matplotlib haute résolution (300 DPI) pour la dynamique globale SEIR / SIR."""
    if not HAS_MATPLOTLIB:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    jours = df_prov_daily["Jour"].values
    s = df_prov_daily["Susceptibles (S)"].values
    i = df_prov_daily["Infectés (I)"].values
    r = df_prov_daily["Rétablis (R)"].values
    
    ax.plot(jours, s, label='Susceptibles (S)', color='#0284c7', linewidth=2.5)
    if est_seir and "Exposés (E)" in df_prov_daily.columns:
        e = df_prov_daily["Exposés (E)"].values
        ax.plot(jours, e, label='Exposés (E)', color='#f59e0b', linewidth=2.5)
    ax.plot(jours, i, label='Infectés (I)', color='#ef4444', linewidth=3.0)
    ax.plot(jours, r, label='Rétablis (R)', color='#10b981', linewidth=2.5)
    
    idx_pic = int(np.argmax(i))
    jour_pic = int(jours[idx_pic])
    pic_val = int(i[idx_pic])
    ax.scatter([jour_pic], [pic_val], color='#dc2626', s=70, zorder=5, edgecolors='white', linewidth=1.5)
    offset_x = 10 if jour_pic < len(jours)*0.6 else -25
    ax.annotate(
        f"Pic : {pic_val:,} cas\n(Jour {jour_pic})",
        xy=(jour_pic, pic_val),
        xytext=(jour_pic + offset_x, pic_val * 0.95),
        arrowprops=dict(arrowstyle='->', color='#dc2626', lw=1.5),
        fontsize=9.5, fontweight='bold', color='#991b1b',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#fee2e2', edgecolor='#fca5a5', alpha=0.9)
    )
    
    mod_str = "SEIR" if est_seir else "SIR"
    sub_txt = f"Modèle {mod_str}" + (f" | $R_0 = {r0}$" if r0 else "")
    ax.set_title(f"Dynamique Globale des Compartiments - {nom_maladie} ({nom_province})\n{sub_txt}", 
                 fontsize=13, fontweight='bold', pad=12, color='#0f172a')
    ax.set_xlabel("Jour de Simulation", fontsize=11, fontweight='600', color='#334155', labelpad=8)
    ax.set_ylabel("Nombre d'Individus", fontsize=11, fontweight='600', color='#334155', labelpad=8)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(formateur_milliers_mpl))
    ax.set_xlim(1, max(jours))
    max_y = max(float(np.max(s)), float(np.max(r)), float(np.max(i)))
    ax.set_ylim(0, max_y * 1.05)
    ax.grid(True, linestyle='--', alpha=0.7, color='#e2e8f0')
    ax.set_facecolor('#f8fafc')
    fig.patch.set_facecolor('#ffffff')
    ax.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9.5)
    plt.tight_layout()
    return fig

def creer_figure_matplotlib_capacite(df_synth, nom_province, figsize=(13, 5.8), dpi=300):
    """Génère un diagramme en barres groupées Matplotlib haute résolution des capacités hospitalières."""
    if not HAS_MATPLOTLIB:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    zones = df_synth["Zone de Santé"].values
    lits_disp = df_synth["Cpt Lits"].values
    lits_req = df_synth["CapRequisPic"].values
    x = np.arange(len(zones))
    width = 0.38
    ax.bar(x - width/2, lits_disp, width, label='Lits Disponibles (Capacité Existante)', 
           color='#3b82f6', edgecolor='#1d4ed8', linewidth=0.8, alpha=0.9)
    ax.bar(x + width/2, lits_req, width, label='Lits Requis au Pic Épidémique', 
           color='#ef4444', edgecolor='#b91c1c', linewidth=0.8, alpha=0.9)
    ax.set_title(f"Comparaison Capacitaire : Lits Disponibles vs Lits Requis au Pic ({nom_province})", 
                 fontsize=13, fontweight='bold', pad=15, color='#0f172a')
    ax.set_xlabel("Zone de Santé", fontsize=11, fontweight='600', color='#334155', labelpad=10)
    ax.set_ylabel("Nombre de Lits", fontsize=11, fontweight='600', color='#334155', labelpad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(zones, rotation=45, ha='right', fontsize=8.5, fontweight='500', color='#1e293b')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(formateur_milliers_mpl))
    ax.grid(True, axis='y', linestyle='--', alpha=0.6, color='#cbd5e1')
    ax.set_facecolor('#f8fafc')
    fig.patch.set_facecolor('#ffffff')
    ax.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=10)
    
    top_deficits = df_synth.sort_values(by="Déficit cpt", ascending=False).head(3)
    for _, row in top_deficits.iterrows():
        z_matches = np.where(zones == row["Zone de Santé"])[0]
        if len(z_matches) > 0:
            z_idx = z_matches[0]
            def_val = int(row["Déficit cpt"])
            req_val = float(row["CapRequisPic"])
            ax.annotate(
                f"-{def_val:,}",
                xy=(z_idx + width/2, req_val),
                xytext=(z_idx + width/2, req_val + max(lits_req)*0.03),
                ha='center', fontsize=8, fontweight='bold', color='#b91c1c'
            )
    plt.tight_layout()
    return fig

def creer_figure_matplotlib_zone(df_zone_long, nom_zone, figsize=(8, 4.5), dpi=300):
    """Génère la courbe Matplotlib locale d'une zone de santé."""
    if not HAS_MATPLOTLIB:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    jours = df_zone_long["Jour"].values
    inf = df_zone_long["Infectés (I)"].values
    occ = df_zone_long["Lits Occupés"].values
    ax.plot(jours, inf, label='Infectés (I)', color='#ef4444', linewidth=2.5)
    ax.plot(jours, occ, label='Lits Occupés', color='#a855f7', linewidth=2.0, linestyle='--')
    ax.set_title(f"Dynamique Locale & Lits Occupés - {nom_zone}", fontsize=12, fontweight='bold', pad=10, color='#0f172a')
    ax.set_xlabel("Jour", fontsize=10.5, fontweight='600', color='#334155')
    ax.set_ylabel("Nombre de Cas / Lits", fontsize=10.5, fontweight='600', color='#334155')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(formateur_milliers_mpl))
    ax.grid(True, linestyle='--', alpha=0.6, color='#e2e8f0')
    ax.set_facecolor('#f8fafc')
    fig.patch.set_facecolor('#ffffff')
    ax.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9.5)
    plt.tight_layout()
    return fig

def creer_figure_matplotlib_optimisation(res_opt, figsize=(10, 5), dpi=300):
    """Génère le graphique d'optimisation capacitaire double axe Matplotlib."""
    if not HAS_MATPLOTLIB:
        return None
    fig, ax1 = plt.subplots(figsize=figsize, dpi=dpi)
    df_opt = res_opt["df_opt"]
    taux_nums = df_opt["Taux_Num"].values
    jours_sat = df_opt["Jours de Saturation"].values
    deficits = df_opt["Déficit Max (Lits)"].values
    
    color_bar = '#ef4444'
    ax1.bar(taux_nums, jours_sat, width=3.2, color=color_bar, alpha=0.75, label='Jours de Saturation')
    ax1.set_xlabel("Taux d'Hospitalisation des Infectés (%)", fontsize=11, fontweight='600', color='#334155', labelpad=8)
    ax1.set_ylabel("Jours de Saturation Hospitalière (Jours)", fontsize=11, fontweight='600', color=color_bar, labelpad=8)
    ax1.tick_params(axis='y', labelcolor=color_bar)
    
    ax2 = ax1.twinx()
    color_line = '#d97706'
    ax2.plot(taux_nums, deficits, color=color_line, linewidth=2.5, marker='o', markersize=5, label='Pic de Déficit de Lits')
    ax2.set_ylabel("Déficit Maximal en Lits au Pic", fontsize=11, fontweight='600', color=color_line, labelpad=8)
    ax2.tick_params(axis='y', labelcolor=color_line)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(formateur_milliers_mpl))
    
    taux_opt_val = res_opt["taux_optimal_pct"]
    taux_act_val = res_opt["taux_actuel_pct"]
    if 0 < taux_opt_val <= 100:
        ax1.axvline(x=taux_opt_val, color='#10b981', linestyle='--', linewidth=2.0, label=f"Optimum: {taux_opt_val}% (0j sat)")
    ax1.axvline(x=taux_act_val, color='#0284c7', linestyle=':', linewidth=2.0, label=f"Taux actuel: {taux_act_val}%")
    
    ax1.set_title("Arbitrage & Optimisation : Jours de Saturation vs Déficit de Lits", fontsize=12.5, fontweight='bold', pad=12, color='#0f172a')
    ax1.grid(True, linestyle='--', alpha=0.5, color='#e2e8f0')
    ax1.set_facecolor('#f8fafc')
    fig.patch.set_facecolor('#ffffff')
    plt.tight_layout()
    return fig

def creer_carte_matplotlib_propagation(sim_data, j_day, figsize=(9, 7), dpi=300):
    """Génère une carte géographique de propagation 2D Matplotlib."""
    if not HAS_MATPLOTLIB:
        return None
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    df_synth = sim_data["df_synth"]
    df_long = sim_data["df_long"]
    prov_nom = sim_data["province"]
    maladie_nom = sim_data["maladie_meta"]["Nom"]
    
    df_j = df_long[df_long["Jour"] == j_day]
    if df_j.empty:
        df_merged = df_synth.copy()
        df_merged["Infectés (I)"] = 0
        df_merged["Lits Occupés"] = 0
    else:
        df_merged = pd.merge(df_synth, df_j, on="Zone de Santé", how="left")
        df_merged["Infectés (I)"] = df_merged["Infectés (I)"].fillna(0).astype(int)
        df_merged["Lits Occupés"] = df_merged["Lits Occupés"].fillna(0).astype(int)
        
    ax.set_facecolor('#f1f5f9')
    fig.patch.set_facecolor('#ffffff')
    
    categories = {
        'saine': {'x': [], 'y': [], 's': [], 'color': '#10b981', 'label': 'Saine (Non touchée)'},
        'active_ok': {'x': [], 'y': [], 's': [], 'color': '#f97316', 'label': 'Active (Capacité OK)'},
        'saturation': {'x': [], 'y': [], 's': [], 'color': '#ef4444', 'label': 'Active (Saturation Lits)'},
        'foyer': {'x': [], 'y': [], 's': [], 'color': '#b91c1c', 'label': '★ Épicentre / Foyer Initial'},
    }
    
    for idx, row in df_merged.iterrows():
        lat = float(row["Latitude"]) if pd.notna(row["Latitude"]) else 0.0
        lon = float(row["Longitude"]) if pd.notna(row["Longitude"]) else 0.0
        inf = int(row["Infectés (I)"])
        cpt = int(row["Cpt Lits"])
        occ = int(row["Lits Occupés"])
        foyer = bool(row["est_foyer"])
        deficit = max(0, occ - cpt)
        base_size = 70 + int(np.sqrt(max(1, inf)) * 3.5) if inf > 0 else 55
        
        if inf == 0:
            categories['saine']['x'].append(lon)
            categories['saine']['y'].append(lat)
            categories['saine']['s'].append(base_size)
        elif foyer and inf > 0:
            categories['foyer']['x'].append(lon)
            categories['foyer']['y'].append(lat)
            categories['foyer']['s'].append(max(180, base_size))
        elif deficit > 0:
            categories['saturation']['x'].append(lon)
            categories['saturation']['y'].append(lat)
            categories['saturation']['s'].append(base_size)
        else:
            categories['active_ok']['x'].append(lon)
            categories['active_ok']['y'].append(lat)
            categories['active_ok']['s'].append(base_size)
            
    for cat_key, cat_data in categories.items():
        if cat_data['x']:
            if cat_key == 'foyer':
                ax.scatter(cat_data['x'], cat_data['y'], s=cat_data['s'], color=cat_data['color'], 
                           label=cat_data['label'], edgecolors='#7f1d1d', linewidth=2.0, alpha=0.9, marker='*', zorder=6)
            elif cat_key == 'saturation':
                ax.scatter(cat_data['x'], cat_data['y'], s=cat_data['s'], color=cat_data['color'], 
                           label=cat_data['label'], edgecolors='#991b1b', linewidth=1.2, alpha=0.85, zorder=5)
            elif cat_key == 'active_ok':
                ax.scatter(cat_data['x'], cat_data['y'], s=cat_data['s'], color=cat_data['color'], 
                           label=cat_data['label'], edgecolors='#c2410c', linewidth=1.0, alpha=0.85, zorder=4)
            else:
                ax.scatter(cat_data['x'], cat_data['y'], s=cat_data['s'], color=cat_data['color'], 
                           label=cat_data['label'], edgecolors='#047857', linewidth=0.8, alpha=0.75, zorder=3)
                
    zones_a_annoter = ['Bunia', 'Gethy', 'Mahagi', 'Aru', 'Mambasa', 'Komanda', 'Tchomia', 'Mongbalu']
    for idx, row in df_merged.iterrows():
        z_name = str(row["Zone de Santé"])
        if z_name in zones_a_annoter or row["est_foyer"]:
            ax.annotate(
                z_name,
                xy=(row["Longitude"], row["Latitude"]),
                xytext=(row["Longitude"] + 0.05, row["Latitude"] + 0.04),
                fontsize=8.5, fontweight='bold' if row["est_foyer"] else 'normal', color='#0f172a',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#ffffff', edgecolor='#cbd5e1', alpha=0.85)
            )
            
    tot_inf = int(df_merged["Infectés (I)"].sum())
    tot_occ = int(df_merged["Lits Occupés"].sum())
    nb_actives = int((df_merged["Infectés (I)"] > 0).sum())
    ax.set_title(f"Propagation Spatio-Temporelle : {maladie_nom} - {prov_nom} (Jour {j_day})\n"
                 f"Infectés actifs : {tot_inf:,} | Lits occupés : {tot_occ:,} | Zones actives : {nb_actives}/{len(df_merged)}", 
                 fontsize=12, fontweight='bold', pad=12, color='#0f172a')
    ax.set_xlabel("Longitude (°E)", fontsize=10.5, fontweight='600', color='#334155', labelpad=6)
    ax.set_ylabel("Latitude (°N)", fontsize=10.5, fontweight='600', color='#334155', labelpad=6)
    ax.grid(True, linestyle=':', alpha=0.5, color='#94a3b8')
    ax.legend(loc='lower right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9)
    plt.tight_layout()
    return fig

def exporter_figure_vers_bytes(fig, format_img='png', dpi=300):
    """Convertit une figure Matplotlib en flux binaire BytesIO."""
    buf = io.BytesIO()
    fig.savefig(buf, format=format_img, dpi=dpi, bbox_inches='tight')
    buf.seek(0)
    return buf

def generer_archive_toutes_figures_matplotlib(sim_data, res_opt=None, dpi=300):
    """Génère une archive ZIP en mémoire contenant toutes les figures du rapport en PNG 300 DPI et PDF vectoriel."""
    zip_buf = io.BytesIO()
    prov_clean = sim_data["province"].strip().lower().replace(" ", "_")
    mal_clean = sim_data["maladie_meta"]["Nom"].strip().lower().replace(" ", "_")
    est_seir = (sim_data["maladie_meta"]["Modele"] == "SEIR")
    r0 = sim_data["maladie_meta"].get("Ro")
    
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Figure Dynamique Globale
        fig1 = creer_figure_matplotlib_dynamique_globale(
            sim_data["df_prov_daily"], sim_data["province"], sim_data["maladie_meta"]["Nom"], est_seir, r0=r0, dpi=dpi
        )
        if fig1:
            zf.writestr(f"figure1_dynamique_globale_{mal_clean}_{prov_clean}.png", exporter_figure_vers_bytes(fig1, 'png', dpi).read())
            zf.writestr(f"figure1_dynamique_globale_{mal_clean}_{prov_clean}.pdf", exporter_figure_vers_bytes(fig1, 'pdf', dpi).read())
            plt.close(fig1)
            
        # 2. Figure Comparatif Capacité Lits
        fig2 = creer_figure_matplotlib_capacite(sim_data["df_synth"], sim_data["province"], dpi=dpi)
        if fig2:
            zf.writestr(f"figure2_capacite_lits_{prov_clean}.png", exporter_figure_vers_bytes(fig2, 'png', dpi).read())
            zf.writestr(f"figure2_capacite_lits_{prov_clean}.pdf", exporter_figure_vers_bytes(fig2, 'pdf', dpi).read())
            plt.close(fig2)
            
        # 3. Figure Carte Jour 1
        fig3 = creer_carte_matplotlib_propagation(sim_data, j_day=1, dpi=dpi)
        if fig3:
            zf.writestr(f"figure3_carte_propagation_jour1_{prov_clean}.png", exporter_figure_vers_bytes(fig3, 'png', dpi).read())
            zf.writestr(f"figure3_carte_propagation_jour1_{prov_clean}.pdf", exporter_figure_vers_bytes(fig3, 'pdf', dpi).read())
            plt.close(fig3)
            
        # 4. Figure Carte Jour 25 ou Jour du pic
        max_j = int(sim_data["df_long"]["Jour"].max())
        j_eval = min(25, max_j)
        fig4 = creer_carte_matplotlib_propagation(sim_data, j_day=j_eval, dpi=dpi)
        if fig4:
            zf.writestr(f"figure4_carte_propagation_jour{j_eval}_{prov_clean}.png", exporter_figure_vers_bytes(fig4, 'png', dpi).read())
            zf.writestr(f"figure4_carte_propagation_jour{j_eval}_{prov_clean}.pdf", exporter_figure_vers_bytes(fig4, 'pdf', dpi).read())
            plt.close(fig4)
            
        # 5. Figure Optimisation (si disponible)
        if res_opt:
            fig5 = creer_figure_matplotlib_optimisation(res_opt, dpi=dpi)
            if fig5:
                zf.writestr(f"figure5_optimisation_capacitaire_{prov_clean}.png", exporter_figure_vers_bytes(fig5, 'png', dpi).read())
                zf.writestr(f"figure5_optimisation_capacitaire_{prov_clean}.pdf", exporter_figure_vers_bytes(fig5, 'pdf', dpi).read())
                plt.close(fig5)
                
    zip_buf.seek(0)
    return zip_buf

def sauvegarder_toutes_figures_dossier(sim_data, res_opt=None, dossier="figures_rapport_matplotlib", dpi=300):
    """Enregistre toutes les figures générées avec Matplotlib directement dans un sous-dossier du projet."""
    os.makedirs(dossier, exist_ok=True)
    prov_clean = sim_data["province"].strip().lower().replace(" ", "_")
    mal_clean = sim_data["maladie_meta"]["Nom"].strip().lower().replace(" ", "_")
    est_seir = (sim_data["maladie_meta"]["Modele"] == "SEIR")
    r0 = sim_data["maladie_meta"].get("Ro")
    chemins_generes = []

    # 1. Dynamique globale
    fig1 = creer_figure_matplotlib_dynamique_globale(sim_data["df_prov_daily"], sim_data["province"], sim_data["maladie_meta"]["Nom"], est_seir, r0=r0, dpi=dpi)
    if fig1:
        p1 = os.path.join(dossier, f"figure_dynamique_globale_{mal_clean}_{prov_clean}.png")
        fig1.savefig(p1, dpi=dpi, bbox_inches='tight')
        plt.close(fig1)
        chemins_generes.append(p1)

    # 2. Capacité lits
    fig2 = creer_figure_matplotlib_capacite(sim_data["df_synth"], sim_data["province"], dpi=dpi)
    if fig2:
        p2 = os.path.join(dossier, f"figure_capacite_lits_{prov_clean}.png")
        fig2.savefig(p2, dpi=dpi, bbox_inches='tight')
        plt.close(fig2)
        chemins_generes.append(p2)

    # 3. Carte Jour 1
    fig3 = creer_carte_matplotlib_propagation(sim_data, j_day=1, dpi=dpi)
    if fig3:
        p3 = os.path.join(dossier, f"figure_carte_jour1_{prov_clean}.png")
        fig3.savefig(p3, dpi=dpi, bbox_inches='tight')
        plt.close(fig3)
        chemins_generes.append(p3)

    # 4. Carte Jour 25
    max_j = int(sim_data["df_long"]["Jour"].max())
    j_eval = min(25, max_j)
    fig4 = creer_carte_matplotlib_propagation(sim_data, j_day=j_eval, dpi=dpi)
    if fig4:
        p4 = os.path.join(dossier, f"figure_carte_jour{j_eval}_{prov_clean}.png")
        fig4.savefig(p4, dpi=dpi, bbox_inches='tight')
        plt.close(fig4)
        chemins_generes.append(p4)

    # 5. Optimisation
    if res_opt:
        fig5 = creer_figure_matplotlib_optimisation(res_opt, dpi=dpi)
        if fig5:
            p5 = os.path.join(dossier, f"figure_optimisation_capacite_{prov_clean}.png")
            fig5.savefig(p5, dpi=dpi, bbox_inches='tight')
            plt.close(fig5)
            chemins_generes.append(p5)

    return chemins_generes



# 4. APPLICATION PRINCIPALE

def main():
    moteur_sql = me_connecter_base()
    if not moteur_sql:
        st.stop()

    # Chargement dynamique initial depuis MySQL
    provinces = charger_provinces(moteur_sql)
    df_maladies = charger_maladies(moteur_sql)

    st.sidebar.markdown("---")
    st.sidebar.markdown("Paramètres de Simulation")

    # 1. Sélection de la Province
    province_choisie = st.sidebar.selectbox(
        "Province :",
        options=provinces,
        index=0 if provinces else None
    )

    # 2. Sélection de l'Épicentre / Foyer Initial (Aléatoire par défaut)
    st.sidebar.markdown("Épicentre(Foyer Initial):")
    mode_epicentre = st.sidebar.radio(
        "Mode d'épicentre :",
        options=["Aléatoire", "Personnalisé"],
        index=0,
        label_visibility="collapsed",
        help="En mode aléatoire, le foyer initial (infrastructure / zone de départ) est tiré au sort parmi toutes les structures de la province."
    )

    seed_val = None
    if mode_epicentre.startswith("Aléatoire"):
        infra_choisie = "ALEATOIRE"
        
        col_tirage1, col_tirage2 = st.sidebar.columns([1.2, 1])
        with col_tirage1:
            if st.button("Tirer au sort", use_container_width=True, help="Tirer un nouvel épicentre au hasard"):
                st.session_state["epicentre_seed"] = int(np.random.randint(1, 1000000))
                st.session_state.pop("sim_data", None)
                st.rerun()

        with col_tirage2:
            fixer_graine = st.checkbox("Fixer graine", value=False, help="Permet de fixer une graine pour reproduire un tirage")

        if fixer_graine:
            seed_val = st.sidebar.number_input("Graine (seed) :", value=st.session_state.get("epicentre_seed", 42), step=1)
            st.session_state["epicentre_seed"] = int(seed_val)
        else:
            if "epicentre_seed" not in st.session_state:
                st.session_state["epicentre_seed"] = int(np.random.randint(1, 1000000))
            seed_val = st.session_state["epicentre_seed"]

    else:
        if province_choisie:
            infrastructures_disponibles = charger_infrastructures_par_province(moteur_sql, province_choisie)
        else:
            infrastructures_disponibles = []

        infra_choisie = st.sidebar.selectbox(
            "Infrastructure / Foyer de départ :",
            options=infrastructures_disponibles if infrastructures_disponibles else ["Aucune infrastructure"],
            index=0 if infrastructures_disponibles else 0
        )

    # 3. Sélection de la Maladie
    liste_maladies = df_maladies['NomMaladie'].str.strip().tolist() if not df_maladies.empty else []
    maladie_choisie = st.sidebar.selectbox(
        "Maladie :",
        options=liste_maladies,
        index=0 if liste_maladies else 0
    )

    # Valeur par défaut du taux d'hospitalisation selon la maladie choisie
    taux_hosp_defaut = 5
    if not df_maladies.empty and maladie_choisie:
        filtre_m = df_maladies['NomMaladie'].astype(str).str.strip().str.lower() == maladie_choisie.strip().lower()
        match_m = df_maladies[filtre_m]
        if not match_m.empty:
            val_hosp = match_m.iloc[0].get('TauxHospitalisation')
            if pd.notna(val_hosp):
                val_hosp_float = float(val_hosp)
                taux_hosp_defaut = int(round(val_hosp_float * 100)) if val_hosp_float <= 1.0 else int(round(val_hosp_float))

    # 4. Taux d'hospitalisation
    taux_hospitalisation_pct = st.sidebar.slider(
        "Taux d'hospitalisation (%) :",
        min_value=1,
        max_value=100,
        value=min(100, max(1, taux_hosp_defaut)),
        step=1,
        format="%d%%",
        help="Pourcentage des individus infectés nécessitant une hospitalisation (lit d'hôpital)."
    )
    taux_hosp_val = taux_hospitalisation_pct / 100.0

    # 5. Durée de simulation
    duree_jours = st.sidebar.slider(
        "Durée de simulation (jours) :",
        min_value=10,
        max_value=900,
        value=100,
        step=5
    )

    # 6. Proximité & Transmission Inter-Provinciale
    with st.sidebar.expander("Proximité Inter-Provinciale", expanded=True):
        activer_interprov = st.checkbox(
            "Inclure zones des provinces voisines",
            value=True,
            help="Prend en compte les infrastructures des zones de santé d'autres provinces situées à une distance donnée des structures de la province choisie."
        )
        dist_interprov_max = 50
        if activer_interprov:
            dist_interprov_max = st.slider(
                "Distance max inter-provinciale :",
                min_value=5,
                max_value=150,
                value=50,
                step=5,
                format="%d km",
                help="Rayon maximal en kilomètres pour connecter et inclure une infrastructure d'une autre province."
            )

    bouton_lancer = st.sidebar.button("Lancer la Simulation", type="primary", use_container_width=True)

    # Exécution de la simulation
    if "sim_data" not in st.session_state or bouton_lancer:
        if province_choisie and maladie_choisie:
            with st.spinner("Calcul de la simulation épidémiologique et de la mobilité..."):
                res, err = simuler_epidemic_streamlit(
                    engine=moteur_sql,
                    df_maladies=df_maladies,
                    nom_province=province_choisie,
                    nom_infra_depart=infra_choisie,
                    nom_maladie_saisie=maladie_choisie,
                    duree_jours=duree_jours,
                    taux_hospitalisation=taux_hosp_val,
                    seed_epicentre=seed_val,
                    distance_max_interprov_km=dist_interprov_max,
                    inclure_interprovincial=activer_interprov
                )
                if err:
                    st.error(err)
                else:
                    st.session_state["sim_data"] = res

    sim_data = st.session_state.get("sim_data")

    # Affichage du Dashboard
    if sim_data:
        df_synth_map = sim_data["df_synth"]
        df_long_map = sim_data["df_long"]
        df_synth = sim_data.get("df_synth_province", sim_data["df_synth"])
        df_prov_daily = sim_data.get("df_prov_daily_province", sim_data["df_prov_daily"])
        meta = sim_data["maladie_meta"]

        # En-tête
        tag_mode = "Foyer Aléatoire" if sim_data.get("mode_selection_epicentre") == "Aléatoire" else "Foyer Manuel"
        st.markdown(f"""
        <div class="main-header">
            <h1>Epidemia - Dashboard de Simulation ({sim_data['province']})</h1>
            <p>Simulation propagation <b>{meta['Nom']}</b> -- Foyer initial : <b>{sim_data['infra_depart']}</b></p>
        </div>
        """, unsafe_allow_html=True)

        # Calculs KPI
        pop_totale = df_synth["Population"].sum()
        pic_infectes_prov = df_prov_daily["Infectés (I)"].max()
        jour_pic_prov = df_prov_daily.loc[df_prov_daily["Infectés (I)"].idxmax(), "Jour"]
        lits_totaux = df_synth["Cpt Lits"].sum()
        lits_req_pic = df_synth["CapRequisPic"].sum()
        deficit_max = df_synth["Déficit cpt"].sum()
        nb_zones_touchees = len(df_synth[df_synth["t0"] != "Non touchée"])
        total_zones = len(df_synth)

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Population Totale</div>
                <div class="metric-value">{pop_totale:,}</div>
                <div class="metric-sub">{total_zones} Zones de Santé</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Pic d'Infectés</div>
                <div class="metric-value">{pic_infectes_prov:,}</div>
                <div class="metric-sub">Au Jour {jour_pic_prov}</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Capacité Lits Totale</div>
                <div class="metric-value">{lits_totaux:,}</div>
                <div class="metric-sub">Requis au Pic : {lits_req_pic:,}</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Déficit Cumulé</div>
                <div class="metric-value" style="color: {'#ef4444' if deficit_max > 0 else '#10b981'}">{deficit_max:,}</div>
                <div class="metric-sub">Taux Hosp : {int(meta['TauxHosp']*100)}%</div>
            </div>
            """, unsafe_allow_html=True)

        with col5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Zones Touchées</div>
                <div class="metric-value">{nb_zones_touchees} / {total_zones}</div>
                <div class="metric-sub">{int(nb_zones_touchees/total_zones*100)}% du territoire</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Onglets de visualisation
        tab_courbes, tab_carte, tab_sensibilite, tab_tables, tab_export = st.tabs([
            "Courbes Épidémiologiques",
            "Carte Interactive de la Province",
            "Analyse de Sensibilité",
            "Synthèse & Données Détaillées",
            "Exportation Excel"
        ])

        # TAB 1 : Courbes
        with tab_courbes:
            st.subheader("Évolution Temporelle de l'Épidémie")

            if HAS_PLOTLY:
                config_hd = {'toImageButtonOptions': {'format': 'png', 'scale': 3}, 'displaylogo': False}
                col_left, col_right = st.columns([2, 1.25])

                with col_left:
                    fig_prov = go.Figure()
                    fig_prov.add_trace(go.Scatter(
                        x=df_prov_daily["Jour"], y=df_prov_daily["Susceptibles (S)"],
                        mode='lines', name='Susceptibles (S)',
                        line=dict(color='#0284c7', width=2.5, shape='spline'),
                        hovertemplate="Jour %{x}<br>Susceptibles : <b>%{y:,.0f}</b><extra></extra>"
                    ))
                    if "Exposés (E)" in df_prov_daily.columns:
                        fig_prov.add_trace(go.Scatter(
                            x=df_prov_daily["Jour"], y=df_prov_daily["Exposés (E)"],
                            mode='lines', name='Exposés (E)',
                            line=dict(color='#f59e0b', width=2.5, shape='spline'),
                            hovertemplate="Jour %{x}<br>Exposés : <b>%{y:,.0f}</b><extra></extra>"
                        ))
                    fig_prov.add_trace(go.Scatter(
                        x=df_prov_daily["Jour"], y=df_prov_daily["Infectés (I)"],
                        mode='lines', name='Infectés (I)',
                        line=dict(color='#dc2626', width=3.5, shape='spline'),
                        hovertemplate="Jour %{x}<br>Infectés : <b>%{y:,.0f}</b><extra></extra>"
                    ))
                    fig_prov.add_trace(go.Scatter(
                        x=df_prov_daily["Jour"], y=df_prov_daily["Rétablis (R)"],
                        mode='lines', name='Rétablis (R)',
                        line=dict(color='#059669', width=2.5, shape='spline'),
                        hovertemplate="Jour %{x}<br>Rétablis : <b>%{y:,.0f}</b><extra></extra>"
                    ))

                    idx_pic = df_prov_daily["Infectés (I)"].idxmax()
                    jour_pic = int(df_prov_daily.loc[idx_pic, "Jour"])
                    valeur_pic = int(df_prov_daily.loc[idx_pic, "Infectés (I)"])
                    fig_prov.add_annotation(
                        x=jour_pic, y=valeur_pic,
                        text=f"Pic : {valeur_pic:,} cas<br>Jour {jour_pic}",
                        showarrow=True, arrowhead=2, ax=38, ay=-48,
                        bgcolor="#fee2e2", bordercolor="#fca5a5", borderwidth=1,
                        font=dict(color="#991b1b", size=11)
                    )

                    fig_prov.update_layout(
                        title=f"Dynamique Globale - Province de {sim_data['province']}",
                        xaxis=dict(
                            title="Jour de simulation", showgrid=False, showspikes=True,
                            spikemode="across", spikesnap="cursor",
                            rangeselector=dict(buttons=[
                                dict(step="all", label="Tout")
                            ])
                        ),
                        yaxis=dict(
                            title="Nombre d'individus", rangemode="tozero",
                            gridcolor="rgba(148, 163, 184, 0.22)", zeroline=False
                        ),
                        hovermode="x unified",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=520,
                        margin=dict(l=52, r=24, t=76, b=72),
                        font=dict(family="Arial, sans-serif", size=12, color="#334155"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                        hoverlabel=dict(bgcolor="#0f172a", font_size=12),
                        uirevision=f"dynamique-{sim_data['province']}"
                    )

                    st.markdown("<div style='height: 46px;'></div>", unsafe_allow_html=True)
                    st.plotly_chart(fig_prov, use_container_width=True, config=config_hd)

                with col_right:
                    col_label, col_select = st.columns([1, 2])
                    
                    with col_label:
                        st.markdown("<div style='padding-top: 8px; text-align: right;'><b>Capacité par ZS :</b></div>", unsafe_allow_html=True)
                    
                    with col_select:
                        liste_zones = df_synth["Zone de Santé"].tolist()
                        zone_epicentre = sim_data.get("zone_depart")
                        
                        idx_defaut = 0
                        if zone_epicentre and zone_epicentre in liste_zones:
                            idx_defaut = liste_zones.index(zone_epicentre)
                        elif "est_foyer" in df_synth.columns:
                            foyers = df_synth[df_synth["est_foyer"] == True]["Zone de Santé"].tolist()
                            if foyers and foyers[0] in liste_zones:
                                idx_defaut = liste_zones.index(foyers[0])

                        zone_choisie_plot = st.selectbox(
                            "Capacité par ZS:", 
                            options=liste_zones,
                            index=idx_defaut,
                            label_visibility="collapsed"
                        )

                    df_zone_long = sim_data["df_long"][sim_data["df_long"]["Zone de Santé"] == zone_choisie_plot]

                    fig_zone = go.Figure()
                    fig_zone.add_trace(go.Scatter(
                        x=df_zone_long["Jour"], y=df_zone_long["Infectés (I)"],
                        mode='lines', name='Infectés (I)', line=dict(color='#ef4444', width=2.5)
                    ))
                    fig_zone.add_trace(go.Scatter(
                        x=df_zone_long["Jour"], y=df_zone_long["Lits Occupés"],
                        mode='lines', name='Lits Occupés', line=dict(color='#a855f7', width=2, dash='dot')
                    ))

                    fig_zone.update_layout(
                        title=f"Infectés & Lits - {zone_choisie_plot}",
                        xaxis=dict(title="Jour de simulation", showgrid=False),
                        yaxis=dict(
                            title="Nombre d'individus", rangemode="tozero",
                            gridcolor="rgba(148, 163, 184, 0.22)", zeroline=False
                        ),
                        hovermode="x unified",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=510,
                        margin=dict(l=52, r=24, t=76, b=76),
                        font=dict(family="Arial, sans-serif", size=12, color="#334155"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                        hoverlabel=dict(bgcolor="#0f172a", font_size=12)
                    )

                    st.plotly_chart(fig_zone, use_container_width=True, config=config_hd)

                st.markdown("---")
                st.subheader("Comparatif de la Capacité Hospitalière par Zone")

                fig_hosp = go.Figure()
                fig_hosp.add_trace(go.Bar(
                    x=df_synth["Zone de Santé"], y=df_synth["Cpt Lits"],
                    name="Lits disponibles",
                    marker=dict(color="#2563eb", line=dict(color="#1d4ed8", width=1)),
                    hovertemplate="Zone : <b>%{x}</b><br>Lits disponibles : <b>%{y:,.0f}</b><extra></extra>"
                ))
                fig_hosp.add_trace(go.Bar(
                    x=df_synth["Zone de Santé"], y=df_synth["CapRequisPic"],
                    name="Lits requis au pic",
                    marker=dict(color="#e11d48", line=dict(color="#be123c", width=1)),
                    hovertemplate="Zone : <b>%{x}</b><br>Lits requis au pic : <b>%{y:,.0f}</b><extra></extra>"
                ))

                fig_hosp.update_layout(
                    title=dict(
                        text=f"Disponibilité et besoin au pic - {sim_data['province']}",
                        x=0.01, xanchor="left"
                    ),
                    barmode="group",
                    bargap=0.22,
                    bargroupgap=0.08,
                    xaxis=dict(
                        title="Zone de santé", tickangle=-35, showgrid=False,
                        categoryorder="array",
                        categoryarray=df_synth["Zone de Santé"].tolist()
                    ),
                    yaxis=dict(
                        title="Nombre de lits", rangemode="tozero",
                        gridcolor="rgba(148, 163, 184, 0.22)", zeroline=False
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=520,
                    margin=dict(l=52, r=24, t=76, b=110),
                    font=dict(family="Arial, sans-serif", size=12, color="#334155"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    hoverlabel=dict(bgcolor="#0f172a", font_size=12),
                    uirevision=f"capacite-{sim_data['province']}"
                )

                st.plotly_chart(fig_hosp, use_container_width=True, config=config_hd)

            else:
                st.info("Plotly n'est pas disponible. Affichage natif Streamlit.")
                df_chart_data = df_prov_daily.set_index("Jour")
                st.line_chart(df_chart_data[["Susceptibles (S)", "Infectés (I)", "Rétablis (R)"]])

            # SECTION EXPORT & VISUALISATION MATPLOTLIB (QUALITÉ PUBLICATION 300 DPI POUR RAPPORT)
            if False and HAS_MATPLOTLIB:
                st.markdown("---")
                with st.expander("📊 Graphiques Matplotlib Haute Définition (Prêts pour Rapport / Article - Sans Capture d'Écran)", expanded=True):
                    st.markdown("""
                    <div style="background-color: var(--card-bg, #f8fafc); border-left: 4px solid #0284c7; padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: 0.9rem; color: var(--card-text, #1e293b); border: 1px solid var(--card-border, #cbd5e1);">
                        <b>Importation directe depuis Matplotlib :</b> Visualisez et téléchargez directement les figures générées avec <code>matplotlib.pyplot</code> à <b>300 DPI</b> (format publication). Plus besoin de faire de captures d'écran floues ou mal cadrées : ces fichiers s'insèrent directement dans votre rapport Word ou LaTeX.
                    </div>
                    """, unsafe_allow_html=True)
                    
                    tab_mpl1, tab_mpl2, tab_mpl3 = st.tabs([
                        "1. Dynamique Globale SEIR / SIR", 
                        "2. Comparatif Capacitaire Lits", 
                        "3. Dynamique Zone Sélectionnée"
                    ])
                    
                    with tab_mpl1:
                        fig_mpl_dyn = creer_figure_matplotlib_dynamique_globale(
                            df_prov_daily=df_prov_daily,
                            nom_province=sim_data['province'],
                            nom_maladie=meta['Nom'],
                            est_seir=(meta.get("Modele") == "SEIR"),
                            r0=meta.get("Ro"),
                            dpi=140
                        )
                        if fig_mpl_dyn:
                            st.pyplot(fig_mpl_dyn, use_container_width=True)
                            plt.close(fig_mpl_dyn)
                            
                            col_d1, col_d2, col_d3 = st.columns(3)
                            with col_d1:
                                fig_hd_png = creer_figure_matplotlib_dynamique_globale(
                                    df_prov_daily, sim_data['province'], meta['Nom'], (meta.get("Modele") == "SEIR"), r0=meta.get("Ro"), dpi=300
                                )
                                buf_png = exporter_figure_vers_bytes(fig_hd_png, 'png', 300)
                                plt.close(fig_hd_png)
                                st.download_button(
                                    label="📥 Télécharger PNG HD (300 DPI pour Word)",
                                    data=buf_png,
                                    file_name=f"figure1_dynamique_{meta['Nom'].lower()}_{sim_data['province'].lower()}_300dpi.png",
                                    mime="image/png",
                                    use_container_width=True
                                )
                            with col_d2:
                                fig_hd_pdf = creer_figure_matplotlib_dynamique_globale(
                                    df_prov_daily, sim_data['province'], meta['Nom'], (meta.get("Modele") == "SEIR"), r0=meta.get("Ro"), dpi=300
                                )
                                buf_pdf = exporter_figure_vers_bytes(fig_hd_pdf, 'pdf', 300)
                                plt.close(fig_hd_pdf)
                                st.download_button(
                                    label="📥 Télécharger PDF Vectoriel (LaTeX)",
                                    data=buf_pdf,
                                    file_name=f"figure1_dynamique_{meta['Nom'].lower()}_{sim_data['province'].lower()}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            with col_d3:
                                fig_hd_svg = creer_figure_matplotlib_dynamique_globale(
                                    df_prov_daily, sim_data['province'], meta['Nom'], (meta.get("Modele") == "SEIR"), r0=meta.get("Ro"), dpi=300
                                )
                                buf_svg = exporter_figure_vers_bytes(fig_hd_svg, 'svg', 300)
                                plt.close(fig_hd_svg)
                                st.download_button(
                                    label="📥 Télécharger SVG Vectoriel",
                                    data=buf_svg,
                                    file_name=f"figure1_dynamique_{meta['Nom'].lower()}_{sim_data['province'].lower()}.svg",
                                    mime="image/svg+xml",
                                    use_container_width=True
                                )
                                
                    with tab_mpl2:
                        fig_mpl_cap = creer_figure_matplotlib_capacite(df_synth, sim_data['province'], dpi=140)
                        if fig_mpl_cap:
                            st.pyplot(fig_mpl_cap, use_container_width=True)
                            plt.close(fig_mpl_cap)
                            
                            col_c1, col_c2 = st.columns(2)
                            with col_c1:
                                fig_cap_png = creer_figure_matplotlib_capacite(df_synth, sim_data['province'], dpi=300)
                                buf_c_png = exporter_figure_vers_bytes(fig_cap_png, 'png', 300)
                                plt.close(fig_cap_png)
                                st.download_button(
                                    label="📥 Télécharger Comparatif Lits PNG (300 DPI)",
                                    data=buf_c_png,
                                    file_name=f"figure_capacite_lits_{sim_data['province'].lower()}_300dpi.png",
                                    mime="image/png",
                                    use_container_width=True
                                )
                            with col_c2:
                                fig_cap_pdf = creer_figure_matplotlib_capacite(df_synth, sim_data['province'], dpi=300)
                                buf_c_pdf = exporter_figure_vers_bytes(fig_cap_pdf, 'pdf', 300)
                                plt.close(fig_cap_pdf)
                                st.download_button(
                                    label="📥 Télécharger Comparatif Lits PDF (Vectoriel)",
                                    data=buf_c_pdf,
                                    file_name=f"figure_capacite_lits_{sim_data['province'].lower()}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )

                    with tab_mpl3:
                        if 'zone_choisie_plot' in locals() and 'df_zone_long' in locals() and not df_zone_long.empty:
                            fig_mpl_z = creer_figure_matplotlib_zone(df_zone_long, zone_choisie_plot, dpi=140)
                            if fig_mpl_z:
                                st.pyplot(fig_mpl_z, use_container_width=True)
                                plt.close(fig_mpl_z)
                                
                                fig_z_png = creer_figure_matplotlib_zone(df_zone_long, zone_choisie_plot, dpi=300)
                                buf_z_png = exporter_figure_vers_bytes(fig_z_png, 'png', 300)
                                plt.close(fig_z_png)
                                st.download_button(
                                    label=f"📥 Télécharger Courbe {zone_choisie_plot} PNG (300 DPI)",
                                    data=buf_z_png,
                                    file_name=f"figure_zone_{zone_choisie_plot.lower().replace(' ', '_')}_300dpi.png",
                                    mime="image/png",
                                    use_container_width=True
                                )




        # TAB 2 : Carte Interactive & Simulation Spatio-Temporelle
        with tab_carte:
            sim_prov = sim_data['province']
            sim_prov_color = obtenir_couleur_province(sim_prov)
            sim_prov_color_nom = obtenir_nom_couleur_province(sim_prov)
            provinces_incluses = sim_data.get("provinces_incluses", [sim_prov])
            provinces_incluses = list(dict.fromkeys(
                str(province).strip() for province in provinces_incluses if str(province).strip()
            ))
            liaisons_interprov = sim_data.get("liaisons_interprovinciales", [])
            dist_interprov_max = sim_data.get("distance_interprov_max", 0)
            nb_zones_principales = sim_data.get("nb_zones_principales", len(df_synth))
            nb_zones_voisines = sim_data.get("nb_zones_voisines", 0)

            st.subheader(f"Carte de Propagation Épidémique - Province de {sim_prov}")

            center_lat = float(df_synth["Latitude"].dropna().mean()) if (not df_synth.empty and pd.notna(df_synth["Latitude"].mean())) else -4.03
            center_lon = float(df_synth["Longitude"].dropna().mean()) if (not df_synth.empty and pd.notna(df_synth["Longitude"].mean())) else 21.75
            total_zones = len(df_synth)
            sim_duree = int(sim_data["df_long"]["Jour"].max()) if not sim_data["df_long"].empty else duree_jours

            est_seir_sim = (meta.get("Modele") == "SEIR")
            daily_data_dict = {}

            for j_day in range(1, sim_duree + 1):
                df_day_long = df_long_map[df_long_map["Jour"] == j_day]
                df_day_long_prov = df_day_long[df_day_long["Province"].astype(str).str.strip().str.lower() == sim_prov.lower()] if "Province" in df_day_long.columns else df_day_long

                if df_day_long.empty:
                    df_day_merged_map = df_synth_map.copy()
                    df_day_merged_prov = df_synth.copy()
                    df_day_merged_map["Jour"] = j_day
                    df_day_merged_map["Infectés (I)"] = 0
                    df_day_merged_map["Lits Occupés"] = 0
                    df_day_merged_map["Susceptibles (S)"] = df_day_merged_map["Population"]
                    df_day_merged_map["Rétablis (R)"] = 0
                    df_day_merged_prov["Jour"] = j_day
                    df_day_merged_prov["Infectés (I)"] = 0
                    df_day_merged_prov["Lits Occupés"] = 0
                    df_day_merged_prov["Susceptibles (S)"] = df_day_merged_prov["Population"]
                    df_day_merged_prov["Rétablis (R)"] = 0
                    if est_seir_sim:
                        df_day_merged_map["Exposés (E)"] = 0
                        df_day_merged_prov["Exposés (E)"] = 0
                else:
                    # Conserver la colonne Province issue de la synthèse cartographique.
                    # df_day_long contient aussi Province et provoquerait Province_x/Province_y.
                    df_day_long_map = df_day_long.drop(columns=["Province"], errors="ignore")
                    df_day_merged_map = pd.merge(df_synth_map, df_day_long_map, on="Zone de Santé", how="left")
                    if df_synth.empty:
                        df_day_merged_prov = df_day_merged_map.copy()
                    else:
                        df_day_merged_prov = pd.merge(df_synth, df_day_long_prov, on="Zone de Santé", how="left")

                inf_tot_day = int(df_day_merged_prov["Infectés (I)"].fillna(0).sum())
                lits_occ_day = int(df_day_merged_prov["Lits Occupés"].fillna(0).sum())
                zones_active_day = int((df_day_merged_prov["Infectés (I)"].fillna(0) > 0).sum())
                exp_tot_day = int(df_day_merged_prov["Exposés (E)"].fillna(0).sum()) if est_seir_sim and "Exposés (E)" in df_day_merged_prov.columns else 0
                ret_tot_day = int(df_day_merged_prov["Rétablis (R)"].fillna(0).sum())

                day_markers = []

                for idx, row in df_day_merged_map.iterrows():
                    lat_val = row.get("Latitude")
                    lon_val = row.get("Longitude")
                    lat = float(lat_val) if (pd.notna(lat_val) and str(lat_val).strip() != "") else center_lat
                    lon = float(lon_val) if (pd.notna(lon_val) and str(lon_val).strip() != "") else center_lon
                    nom_z = str(row["Zone de Santé"])
                    infra = str(row["Infrastructure Référente"])
                    pop = int(row["Population"]) if pd.notna(row.get("Population")) else 0
                    lits = int(row["Cpt Lits"]) if pd.notna(row.get("Cpt Lits")) else 0
                    est_foyer = bool(row["est_foyer"])
                    t0_val = extract_t0_num(row["t0"])

                    prov_nom = str(row.get("Province") or row.get("province") or sim_prov).strip()
                    prov_color = obtenir_couleur_province(prov_nom)
                    est_voisine = (normaliser_nom_province(prov_nom) != normaliser_nom_province(sim_prov))

                    inf_j = int(row["Infectés (I)"]) if pd.notna(row.get("Infectés (I)")) else 0
                    exp_j = int(row["Exposés (E)"]) if (est_seir_sim and pd.notna(row.get("Exposés (E)"))) else 0
                    s_j = int(row["Susceptibles (S)"]) if pd.notna(row.get("Susceptibles (S)")) else pop
                    r_j = int(row["Rétablis (R)"]) if pd.notna(row.get("Rétablis (R)")) else 0
                    lits_req_j = int(row["Lits Occupés"]) if pd.notna(row.get("Lits Occupés")) else 0
                    defic_j = max(0, lits_req_j - lits)

                    # Détermination précise de la catégorie d'état de la zone
                    if inf_j == 0 and exp_j == 0 and j_day < t0_val:
                        category = "saine"
                        color_hex = "#10b981"
                        badge_icon = "✓"
                        status_title = "Zone Saine (Non touchée)"
                        radius_size = 6
                    elif inf_j == 0 and exp_j == 0 and j_day >= t0_val:
                        category = "retablie"
                        color_hex = "#3b82f6"
                        badge_icon = "R"
                        status_title = f"Zone Rétablie (Épidémie éteinte)<br>({r_j:,} rétablies)"
                        radius_size = 7
                    elif est_foyer and inf_j > 0:
                        category = "foyer"
                        color_hex = "#dc2626"
                        badge_icon = "★"
                        hosp_txt = f"Saturation Hospitalière (Déficit: {defic_j:,} lits)" if defic_j > 0 else "Capacité hospitalière suffisante"
                        status_title = f"Épicentre / Foyer Initial ({inf_j:,} cas) - {hosp_txt}"
                        radius_size = int(max(10, min(42, int(np.sqrt(max(1, inf_j)) * 0.5))))
                    elif defic_j > 0:
                        category = "saturation"
                        color_hex = "#ef4444"
                        badge_icon = "+"
                        status_title = f"Zone Active - Saturation Hospitalière ({inf_j:,} cas<br>Déficit: {defic_j:,} lits)"
                        radius_size = int(max(8, min(45, int(np.sqrt(inf_j) * 0.5))))
                    else:
                        category = "active"
                        color_hex = "#f97316"
                        badge_icon = "▲"
                        status_title = f"Zone Active ({inf_j:,} cas | Capacité OK)"
                        radius_size = int(max(7, min(45, int(np.sqrt(inf_j) * 0.5))))

                    exp_row_html = f"<tr><td><b>Exposés (E) :</b></td><td><b style='color: #a855f7;'>{exp_j:,}</b></td></tr>" if est_seir_sim else ""
                    voisine_badge_html = f"<span style='background: #e0e7ff; color: #4338ca; padding: 1px 5px; border-radius: 6px; font-size: 9px; font-weight: 700; margin-left: 4px;'>Voisine</span>" if est_voisine else ""

                    popup_html = f"""
                    <div style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; min-width: 230px; line-height: 1.4;">
                        <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid {color_hex}; padding-bottom: 5px; margin-bottom: 6px;">
                            <h4 style="margin: 0; color: #0f172a; font-size: 14px; font-weight: 700;">{nom_z}</h4>
                            <span style="background: {color_hex}; color: white; padding: 2px 7px; border-radius: 10px; font-size: 10px; font-weight: 600;">Jour {j_day}</span>
                        </div>
                        <p style="font-size: 11px; margin: 0 0 3px 0; color: #334155;"><b>Province :</b> <span style="color: {prov_color}; font-weight: 700;">● {prov_nom}</span>{voisine_badge_html}</p>
                        <p style="font-size: 11px; margin: 0 0 4px 0; color: #64748b;"><b>Infra ref :</b> {infra}</p>
                        <p style="font-size: 11px; margin: 0 0 6px 0; color: #334155;"><b>Statut :</b> {status_title}</p>
                        <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Population :</b></td><td style="text-align: right;">{pop:,}</td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Susceptibles (S) :</b></td><td style="text-align: right; color: #0284c7;">{s_j:,}</td></tr>
                            {exp_row_html}
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Infectés Actifs (I) :</b></td><td style="text-align: right;"><b style="color: {'#2563eb' if inf_j==0 else '#ef4444'};">{inf_j:,}</b></td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Rétablis (R) :</b></td><td style="text-align: right; color: #10b981;">{r_j:,}</td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Lits Occupés :</b></td><td style="text-align: right;">{lits_req_j:,} / {lits:,}</td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Déficit Lits :</b></td><td style="text-align: right;"><b style="color: {'#ef4444' if defic_j > 0 else '#10b981'};">{defic_j:,}</b></td></tr>
                        </table>
                    </div>
                    """

                    day_markers.append({
                        "lat": lat,
                        "lon": lon,
                        "nom_z": nom_z,
                        "province": prov_nom,
                        "status_txt": f"{nom_z} ({prov_nom}) : {status_title}",
                        "category": category,
                        "color_hex": color_hex,
                        "prov_color": prov_color,
                        "badge_icon": badge_icon,
                        "radius_size": radius_size,
                        "popup_html": popup_html,
                        "inf_j": inf_j,
                        "exp_j": exp_j
                    })

                daily_data_dict[j_day] = {
                    "inf_tot_day": inf_tot_day,
                    "exp_tot_day": exp_tot_day,
                    "ret_tot_day": ret_tot_day,
                    "lits_occ_day": lits_occ_day,
                    "zones_active_day": zones_active_day,
                    "markers": day_markers
                }

            json_daily_data = json.dumps(daily_data_dict)

            # Extraire les coordonnées uniques pour initialiser la carte et le cadrage
            unique_coords = []
            for _, r in df_synth_map.iterrows():
                lat_v = r.get("Latitude")
                lon_v = r.get("Longitude")
                if pd.notna(lat_v) and pd.notna(lon_v):
                    unique_coords.append([float(lat_v), float(lon_v)])
            json_unique_coords = json.dumps(unique_coords)

            html_map_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
                <style>
                    * {{ box-sizing: border-box; }}
                    body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: transparent; color: #1e293b; }}
                    #unified-panel {{ padding: 12px 16px; background: #ffffff; border-radius: 10px; margin-bottom: 12px; border: 1px solid #e2e8f0; border-left: 5px solid #0284c7; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
                    #info-banner-section {{ font-size: 13px; color: #1e293b; font-weight: 500; min-height: 20px; }}
                    .flex-row {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 10px; }}
                    .slider-container {{ flex: 3; min-width: 220px; }}
                    .button-container {{ display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }}
                    .btn {{ padding: 7px 14px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 12px; transition: all 0.2s ease; display: inline-flex; align-items: center; gap: 4px; user-select: none; }}
                    .btn-primary {{ background: #ef4444; color: white; }}
                    .btn-primary:hover {{ background: #dc2626; transform: translateY(-1px); }}
                    .btn-secondary {{ background: #0284c7; color: white; }}
                    .btn-secondary:hover {{ background: #0369a1; transform: translateY(-1px); }}
                    .btn-neutral {{ background: #e2e8f0; color: #1e293b; }}
                    .btn-neutral:hover {{ background: #cbd5e1; }}
                    .speed-select {{ padding: 6px 10px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; font-weight: 600; background: white; cursor: pointer; }}
                    input[type=range] {{ width: 100%; accent-color: #ef4444; cursor: pointer; }}
                    
                    #map-wrapper {{ position: relative; width: 100%; height: 560px; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.08); border: 1px solid #cbd5e1; background: #e5e7eb; }}
                    #map {{ width: 100%; height: 100%; }}

                    .map-toolbar {{
                        position: absolute;
                        top: 14px;
                        right: 14px;
                        z-index: 1001;
                        display: flex;
                        align-items: center;
                        gap: 4px;
                        padding: 5px;
                        background: rgba(255, 255, 255, 0.96);
                        border: 1px solid #cbd5e1;
                        border-radius: 8px;
                        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.18);
                        backdrop-filter: blur(8px);
                    }}
                    .map-tool {{
                        width: 32px;
                        height: 32px;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        padding: 0;
                        border: 1px solid transparent;
                        border-radius: 6px;
                        background: transparent;
                        color: #334155;
                        cursor: pointer;
                        transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
                    }}
                    .map-tool:hover, .map-tool.active {{
                        background: #e0f2fe;
                        border-color: #7dd3fc;
                        color: #0369a1;
                    }}
                    .map-tool svg {{ width: 17px; height: 17px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
                    .toolbar-divider {{ width: 1px; height: 22px; background: #cbd5e1; margin: 0 2px; }}
                    .map-toolbar-hint {{ position: absolute; top: 52px; right: 0; display: none; white-space: nowrap; padding: 5px 8px; border-radius: 5px; background: rgba(15, 23, 42, 0.9); color: #fff; font-size: 11px; pointer-events: none; }}
                    .map-toolbar.selection-mode .map-toolbar-hint {{ display: block; }}
                    
                    /* Légende Flottante Interactive */
                    .map-legend-box {{
                        position: absolute;
                        bottom: 20px;
                        right: 20px;
                        z-index: 1000;
                        background: rgba(255, 255, 255, 0.95);
                        backdrop-filter: blur(8px);
                        border-radius: 8px;
                        padding: 10px 14px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        border: 1px solid #cbd5e1;
                        font-size: 11px;
                        max-width: 270px;
                        pointer-events: auto;
                    }}
                    .legend-title {{ font-weight: 700; margin-bottom: 6px; color: #0f172a; font-size: 12px; }}
                    .legend-item {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
                    .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}

                    /* Marqueur Pin SVG personnalisé */
                    .custom-svg-pin {{
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: transform 0.2s ease;
                        cursor: pointer;
                    }}
                    .custom-svg-pin:hover {{
                        transform: scale(1.3);
                        z-index: 9999 !important;
                    }}
                    
                    /* Animation radar pulsation */
                    @keyframes pulse-radar {{
                        0% {{ transform: scale(0.92); opacity: 0.95; }}
                        50% {{ transform: scale(1.28); opacity: 0.45; }}
                        100% {{ transform: scale(0.92); opacity: 0.95; }}
                    }}
                    .radar-active {{
                        animation: pulse-radar 1.5s infinite ease-in-out;
                    }}

                    @media (prefers-color-scheme: dark) {{
                        body {{ color: #f8fafc; }}
                        #unified-panel {{ background: #1e293b !important; border-color: #334155 !important; color: #f8fafc !important; }}
                        #info-banner-section {{ color: #f8fafc !important; }}
                        .map-legend-box {{ background: rgba(30, 41, 59, 0.95) !important; border-color: #475569 !important; color: #f8fafc !important; }}
                        .legend-title {{ color: #f8fafc !important; }}
                        .btn-neutral {{ background: #334155; color: #f8fafc; }}
                        .btn-neutral:hover {{ background: #475569; }}
                        .speed-select {{ background: #334155; color: #f8fafc; border-color: #475569; }}
                        label {{ color: #f8fafc !important; }}
                    }}
                </style>
            </head>
            <body>
                <div id="unified-panel">
                    <div id="info-banner-section">
                        <span id="banner-text">Chargement des données cartographiques...</span>
                    </div>
                    <div class="flex-row">
                        <div class="slider-container">
                            <label style="font-size: 13px; font-weight: 600; display: block; margin-bottom: 4px;">
                                Jour de simulation : <span id="lbl-jour" style="font-weight: 700; color: #ef4444;">1</span> / {sim_duree}
                            </label>
                            <input type="range" id="slider-day" min="1" max="{sim_duree}" value="1" oninput="setDay(parseInt(this.value))" />
                        </div>
                        <div class="button-container">
                            <button id="btn-play" class="btn btn-neutral" onclick="togglePlay()">▶️ Lancer propagation</button>
                            <button class="btn btn-neutral" onclick="resetDay()">⏪ Jour 1</button>
                            <select id="sel-speed" class="speed-select" onchange="changeSpeed(this.value)">
                                <option value="350">0.5x (Lent)</option>
                                <option value="180" selected>1.0x (Normal)</option>
                                <option value="90">2.0x (Rapide)</option>
                                <option value="40">4.0x (Très rapide)</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div id="map-wrapper">
                    <div id="map"></div>
                    <div class="map-toolbar" id="map-toolbar" aria-label="Barre d'outils de navigation">
                        <button class="map-tool" type="button" title="Download plot as a PNG" aria-label="Download plot as a PNG" onclick="downloadMapPng()">
                            <svg viewBox="0 0 24 24"><path d="M12 3v12"></path><path d="m7 10 5 5 5-5"></path><path d="M5 21h14"></path></svg>
                        </button>
                        <button class="map-tool" id="tool-zoom-area" type="button" title="Zoom par zone" aria-label="Zoom par zone" onclick="setMapMode('zoom')">
                            <svg viewBox="0 0 24 24"><path d="M4 9V5a1 1 0 0 1 1-1h4"></path><path d="M15 4h3a1 1 0 0 1 1 1v4"></path><path d="M20 15v3a1 1 0 0 1-1 1h-4"></path><path d="M9 20H5a1 1 0 0 1-1-1v-4"></path><circle cx="12" cy="12" r="3"></circle></svg>
                        </button>
                        <button class="map-tool active" id="tool-pan" type="button" title="Déplacement / Panoramique" aria-label="Déplacement / Panoramique" onclick="setMapMode('pan')">
                            <svg viewBox="0 0 24 24"><path d="M7 11V6a1.5 1.5 0 0 1 3 0v4"></path><path d="M10 10V4.5a1.5 1.5 0 0 1 3 0V10"></path><path d="M13 10V6a1.5 1.5 0 0 1 3 0v5"></path><path d="M16 11V8.5a1.5 1.5 0 0 1 3 0V14c0 4-2 6-6 6h-1c-2 0-3-1-4-2l-3-3a1.5 1.5 0 0 1 2-2l2 1.5"></path></svg>
                        </button>
                        <button class="map-tool" type="button" title="Ajuster à l'écran" aria-label="Ajuster à l'écran" onclick="fitProvinceBounds()">
                            <svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3"></path><path d="m9 9 3-3 3 3M9 15l3 3 3-3"></path></svg>
                        </button>
                        <button class="map-tool" type="button" title="Réinitialiser la vue" aria-label="Réinitialiser la vue" onclick="resetMapView()">
                            <svg viewBox="0 0 24 24"><path d="m3 11 9-8 9 8"></path><path d="M5 10v10h14V10M9 20v-6h6v6"></path></svg>
                        </button>
                        <button class="map-tool" id="tool-select" type="button" title="Sélection de zone / Cadre" aria-label="Sélection de zone / Cadre" onclick="setMapMode('select')">
                            <svg viewBox="0 0 24 24"><path d="M4 9V5a1 1 0 0 1 1-1h4"></path><path d="M15 4h3a1 1 0 0 1 1 1v4"></path><path d="M20 15v3a1 1 0 0 1-1 1h-4"></path><path d="M9 20H5a1 1 0 0 1-1-1v-4"></path><path d="M8 8h8v8H8z"></path></svg>
                        </button>
                        <span class="map-toolbar-hint">Faites glisser un cadre sur la carte</span>
                    </div>
                    <div class="map-legend-box">
                        <div class="legend-title">Légende épidémiologique</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #10b981;"></span> Saine (Non touchée)</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #dc2626; border: 2px solid #fff; box-shadow: 0 0 4px red;"></span> ★ Foyer Initial / Épicentre</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #ef4444;"></span> ✚ Active (Saturation Lits)</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #f97316;"></span> ▲ Active (Capacité OK)</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #3b82f6;"></span> 🛡️ Rétablie (0 cas actif)</div>
                    </div>
                </div>

                <script>
                    const dailyData = {json_daily_data};
                    const uniqueCoords = {json_unique_coords};
                    const totalZones = {total_zones};
                    const totalDays = {sim_duree};
                    let currentDay = 1;
                    let isPlaying = false;
                    let playSpeed = 180;
                    let timer = null;
                    let mapMode = 'pan';
                    let dragStart = null;
                    let selectionRectangle = null;
                    const initialCenter = [{center_lat}, {center_lon}];
                    const initialZoom = 8;

                    // Initialisation Leaflet avec options de robustesse
                    const map = L.map('map', {{
                        center: [{center_lat}, {center_lon}],
                        zoom: 8,
                        zoomControl: true,
                        preferCanvas: true
                    }});

                    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
                        attribution: '&copy; OpenStreetMap &copy; CARTO',
                        maxZoom: 19,
                        subdomains: 'abcd'
                    }}).addTo(map);

                    // Création de Panes distincts pour assurer que les cercles restent SOUS les épingles (pins)
                    map.createPane('circlesPane');
                    map.getPane('circlesPane').style.zIndex = 400;
                    map.getPane('circlesPane').style.pointerEvents = 'auto';

                    map.createPane('pinsPane');
                    map.getPane('pinsPane').style.zIndex = 600;
                    map.getPane('pinsPane').style.pointerEvents = 'auto';

                    const circlesLayerGroup = L.layerGroup().addTo(map);
                    const pinsLayerGroup = L.layerGroup().addTo(map);

                    // Structure persistante pour conserver les instances de marqueurs par zone
                    const zoneLayers = {{}};

                    // Calcul de l'emprise géographique de la province
                    let provinceBounds = null;
                    if (uniqueCoords && uniqueCoords.length > 0) {{
                        provinceBounds = L.latLngBounds(uniqueCoords);
                    }}

                    function fitProvinceBounds() {{
                        if (provinceBounds && provinceBounds.isValid()) {{
                            map.fitBounds(provinceBounds, {{ padding: [35, 35], maxZoom: 10 }});
                        }} else {{
                            map.setView([{center_lat}, {center_lon}], 8);
                        }}
                    }}

                    function resetMapView() {{
                        clearSelectionRectangle();
                        map.setView(initialCenter, initialZoom);
                    }}

                    function clearSelectionRectangle() {{
                        if (selectionRectangle) {{
                            map.removeLayer(selectionRectangle);
                            selectionRectangle = null;
                        }}
                    }}

                    function setMapMode(mode) {{
                        mapMode = mode;
                        const toolbar = document.getElementById('map-toolbar');
                        const wrapper = document.getElementById('map-wrapper');
                        document.querySelectorAll('.map-tool').forEach(button => button.classList.remove('active'));
                        const activeButton = document.getElementById(mode === 'zoom' ? 'tool-zoom-area' : mode === 'select' ? 'tool-select' : 'tool-pan');
                        if (activeButton) activeButton.classList.add('active');
                        if (toolbar) toolbar.classList.toggle('selection-mode', mode === 'zoom' || mode === 'select');
                        if (wrapper) wrapper.style.cursor = (mode === 'zoom' || mode === 'select') ? 'crosshair' : '';
                        if (mode === 'pan') {{
                            map.dragging.enable();
                        }} else {{
                            map.dragging.disable();
                            clearSelectionRectangle();
                        }}
                    }}

                    function finishMapRectangle(endPoint) {{
                        if (!dragStart || !endPoint) return;
                        const startLatLng = map.containerPointToLatLng(dragStart);
                        const endLatLng = map.containerPointToLatLng(endPoint);
                        const bounds = L.latLngBounds(startLatLng, endLatLng);
                        if (Math.abs(endPoint.x - dragStart.x) < 8 || Math.abs(endPoint.y - dragStart.y) < 8) {{
                            dragStart = null;
                            return;
                        }}
                        clearSelectionRectangle();
                        selectionRectangle = L.rectangle(bounds, {{ color: '#0284c7', weight: 2, fillColor: '#38bdf8', fillOpacity: 0.12, dashArray: '6 4' }}).addTo(map);
                        if (mapMode === 'zoom') {{
                            map.fitBounds(bounds, {{ padding: [24, 24] }});
                            setMapMode('pan');
                        }} else {{
                            const selected = Object.values(zoneLayers).filter(layer => bounds.contains([layer.lat, layer.lon]));
                            const banner = document.getElementById('banner-text');
                            if (banner) banner.innerHTML = `<b style="color: #0369a1;">${{selected.length}}</b> zone(s) sélectionnée(s) dans le cadre`;
                        }}
                        dragStart = null;
                    }}

                    function downloadMapPng() {{
                        const mapWrapper = document.getElementById('map-wrapper');
                        if (!mapWrapper || typeof html2canvas !== 'function') return;
                        html2canvas(mapWrapper, {{ useCORS: true, allowTaint: false, backgroundColor: '#e5e7eb', scale: 2, logging: false }}).then(canvas => {{
                            const link = document.createElement('a');
                            link.download = `carte_propagation_jour_${{currentDay}}.png`;
                            link.href = canvas.toDataURL('image/png');
                            link.click();
                        }}).catch(error => console.error('Impossible de télécharger la carte en PNG:', error));
                    }}

                    function createPinIcon(d) {{
                        const isEpicenter = (d.category === 'foyer');
                        const isSaturated = (d.category === 'saturation');
                        const glowClass = (isEpicenter || isSaturated) ? 'radar-active' : '';
                        const provColor = d.prov_color || d.color_hex;
                        
                        const pinHtml = `
                            <div class="custom-svg-pin ${{glowClass}}" style="width: 32px; height: 32px; position: relative;">
                                <svg width="32" height="32" viewBox="0 0 32 32" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));">
                                    <path d="M16 2C10.48 2 6 6.48 6 12c0 7.5 10 18 10 18s10-10.5 10-18c0-5.52-4.48-10-10-10z" fill="${{d.color_hex}}" stroke="#ffffff" stroke-width="1.8"/>
                                    <circle cx="16" cy="12" r="5.6" fill="${{provColor}}" stroke="#ffffff" stroke-width="0.8" />
                                    <text x="16" y="15" text-anchor="middle" font-size="8.5" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-weight="bold" fill="#ffffff">${{d.badge_icon}}</text>
                                </svg>
                            </div>
                        `;
                        return L.divIcon({{
                            html: pinHtml,
                            className: 'custom-pin-container',
                            iconSize: [32, 32],
                            iconAnchor: [16, 32],
                            popupAnchor: [0, -32]
                        }});
                    }}

                    // Initialisation unique des marqueurs pour chaque zone de santé
                    function initMarkersOnce() {{
                        const firstDayData = dailyData[1] || dailyData[Object.keys(dailyData)[0]];
                        if (!firstDayData || !firstDayData.markers) return;

                        firstDayData.markers.forEach(d => {{
                            try {{
                                // 1. Cercle d'impact épidémiologique
                                const circle = L.circleMarker([d.lat, d.lon], {{
                                    pane: 'circlesPane',
                                    radius: d.radius_size || 6,
                                    color: d.color_hex,
                                    fill: true,
                                    fillColor: d.color_hex,
                                    fillOpacity: (d.category === 'saine' || d.category === 'retablie') ? 0.2 : 0.45,
                                    weight: (d.category === 'foyer' || d.category === 'saturation') ? 2.5 : 1.2
                                }}).addTo(circlesLayerGroup);

                                // 2. Épingle stylisée (Pin)
                                const icon = createPinIcon(d);
                                const marker = L.marker([d.lat, d.lon], {{
                                    pane: 'pinsPane',
                                    icon: icon
                                }})
                                .bindPopup(d.popup_html, {{maxWidth: 320}})
                                .bindTooltip(d.status_txt, {{direction: 'top', offset: [0, -30]}})
                                .addTo(pinsLayerGroup);

                                zoneLayers[d.nom_z] = {{
                                    marker: marker,
                                    circle: circle,
                                    lat: d.lat,
                                    lon: d.lon
                                }};
                            }} catch(err) {{
                                console.error('Erreur initialisation marqueur pour zone:', d.nom_z, err);
                            }}
                        }});
                    }}

                    // Mise à jour fluide des marqueurs existants SANS destruction de couches (élimine la disparition)
                    function renderDay(day) {{
                        if (day < 1) day = 1;
                        if (day > totalDays) day = totalDays;
                        currentDay = day;

                        const slider = document.getElementById('slider-day');
                        if (slider && parseInt(slider.value) !== day) slider.value = day;
                        const lbl = document.getElementById('lbl-jour');
                        if (lbl) lbl.innerText = day;

                        const dayInfo = dailyData[day];
                        if (!dayInfo) return;

                        const banner = document.getElementById('banner-text');
                        if (banner) {{
                            let extraExp = (dayInfo.exp_tot_day > 0) ? ` -- Exposés : <b style="color: #a855f7;">${{dayInfo.exp_tot_day.toLocaleString()}}</b>` : '';
                            let retVal = dayInfo.ret_tot_day !== undefined ? dayInfo.ret_tot_day.toLocaleString() : '0';
                            banner.innerHTML = `Infectés Actifs : <b style="color: #ef4444;">${{dayInfo.inf_tot_day.toLocaleString()}}</b>${{extraExp}} -- Rétablis : <b style="color: #10b981;">${{retVal}}</b> -- Lits Occupés : <b>${{dayInfo.lits_occ_day.toLocaleString()}}</b> -- Zones Actives : <b>${{dayInfo.zones_active_day}}/${{totalZones}}</b>`;
                        }}

                        if (dayInfo.markers && Array.isArray(dayInfo.markers)) {{
                            dayInfo.markers.forEach(d => {{
                                try {{
                                    let zLayer = zoneLayers[d.nom_z];

                                    // Si le marqueur n'existait pas encore, le créer
                                    if (!zLayer) {{
                                        const circle = L.circleMarker([d.lat, d.lon], {{
                                            pane: 'circlesPane',
                                            radius: d.radius_size || 6,
                                            color: d.color_hex,
                                            fill: true,
                                            fillColor: d.color_hex,
                                            fillOpacity: 0.35,
                                            weight: 1.5
                                        }}).addTo(circlesLayerGroup);

                                        const icon = createPinIcon(d);
                                        const marker = L.marker([d.lat, d.lon], {{
                                            pane: 'pinsPane',
                                            icon: icon
                                        }})
                                        .bindPopup(d.popup_html, {{maxWidth: 320}})
                                        .bindTooltip(d.status_txt, {{direction: 'top', offset: [0, -30]}})
                                        .addTo(pinsLayerGroup);

                                        zoneLayers[d.nom_z] = {{ marker: marker, circle: circle, lat: d.lat, lon: d.lon }};
                                        zLayer = zoneLayers[d.nom_z];
                                    }}

                                    // Mise à jour de l'icône, du popup et du tooltip sans détruire le marker
                                    zLayer.marker.setIcon(createPinIcon(d));
                                    zLayer.marker.setPopupContent(d.popup_html);
                                    zLayer.marker.setTooltipContent(d.status_txt);

                                    // Mise à jour du cercle d'impact
                                    zLayer.circle.setRadius(d.radius_size > 0 ? d.radius_size : 6);
                                    zLayer.circle.setStyle({{
                                        color: d.color_hex,
                                        fillColor: d.prov_color || d.color_hex,
                                        fillOpacity: (d.category === 'saine' || d.category === 'retablie') ? 0.2 : 0.45,
                                        weight: (d.category === 'foyer' || d.category === 'saturation') ? 2.5 : 1.2
                                    }});
                                }} catch(err) {{
                                    console.error('Erreur mise à jour zone:', d.nom_z, err);
                                }}
                            }});
                        }}
                    }}

                    function setDay(day) {{
                        if (isPlaying) togglePlay();
                        renderDay(day);
                    }}

                    function stepDay(delta) {{
                        if (isPlaying) togglePlay();
                        renderDay(currentDay + delta);
                    }}

                    function changeSpeed(val) {{
                        playSpeed = parseInt(val);
                        if (isPlaying) {{
                            clearInterval(timer);
                            timer = setInterval(advanceVideo, playSpeed);
                        }}
                    }}

                    function advanceVideo() {{
                        if (currentDay < totalDays) {{
                            renderDay(currentDay + 1);
                        }} else {{
                            togglePlay();
                        }}
                    }}

                    function togglePlay() {{
                        isPlaying = !isPlaying;
                        const btn = document.getElementById('btn-play');
                        if (btn) {{
                            btn.innerText = isPlaying ? "⏸️ Pause Vidéo" : "▶️ Lancer propagation";
                            btn.style.background = isPlaying ? "#eab308" : "#ef4444";
                        }}

                        if (isPlaying) {{
                            if (currentDay >= totalDays) {{
                                renderDay(1);
                            }}
                            timer = setInterval(advanceVideo, playSpeed);
                        }} else {{
                            clearInterval(timer);
                        }}
                    }}

                    function resetDay() {{
                        if (isPlaying) togglePlay();
                        renderDay(1);
                    }}

                    map.on('mousedown', event => {{
                        if (mapMode === 'zoom' || mapMode === 'select') {{
                            dragStart = event.containerPoint;
                            map.getContainer().classList.add('leaflet-dragging');
                        }}
                    }});
                    map.on('mouseup', event => {{
                        if (mapMode === 'zoom' || mapMode === 'select') {{
                            finishMapRectangle(event.containerPoint);
                            map.getContainer().classList.remove('leaflet-dragging');
                        }}
                    }});
                    map.on('mousemove', event => {{
                        if (dragStart && (mapMode === 'zoom' || mapMode === 'select')) {{
                            const bounds = L.latLngBounds(
                                map.containerPointToLatLng(dragStart),
                                event.latlng
                            );
                            clearSelectionRectangle();
                            selectionRectangle = L.rectangle(bounds, {{ color: '#0284c7', weight: 2, fillColor: '#38bdf8', fillOpacity: 0.12, dashArray: '6 4', interactive: false }}).addTo(map);
                        }}
                    }});
                    map.getContainer().addEventListener('mouseleave', () => {{
                        if (dragStart) {{
                            dragStart = null;
                            clearSelectionRectangle();
                            map.getContainer().classList.remove('leaflet-dragging');
                        }}
                    }});

                    // Initialisation des couches et du rendu Jour 1
                    initMarkersOnce();
                    renderDay(1);
                    fitProvinceBounds();

                    // Observateurs avancés de visibilité et redimensionnement (résout le problème des onglets Streamlit cachés)
                    const refreshMapDimensions = () => {{
                        if (map) {{
                            map.invalidateSize();
                        }}
                    }};

                    if (window.ResizeObserver) {{
                        const ro = new ResizeObserver((entries) => {{
                            for (let entry of entries) {{
                                if (entry.contentRect.width > 20 && entry.contentRect.height > 20) {{
                                    refreshMapDimensions();
                                }}
                            }}
                        }});
                        ro.observe(document.getElementById('map'));
                        ro.observe(document.getElementById('map-wrapper'));
                    }}

                    if (window.IntersectionObserver) {{
                        const io = new IntersectionObserver((entries) => {{
                            entries.forEach(e => {{
                                if (e.isIntersecting) {{
                                    refreshMapDimensions();
                                }}
                            }});
                        }});
                        io.observe(document.getElementById('map'));
                    }}

                    // Événements du cycle de vie du navigateur
                    window.addEventListener('resize', refreshMapDimensions);
                    window.addEventListener('focus', refreshMapDimensions);
                    document.addEventListener('visibilitychange', () => {{
                        if (!document.hidden) refreshMapDimensions();
                    }});
                    document.addEventListener('mouseenter', refreshMapDimensions, {{ once: true }});
                    document.addEventListener('mousemove', refreshMapDimensions, {{ once: true }});

                    // Délais de sécurité pour rattraper tout affichage asynchrone dans les onglets Streamlit
                    setTimeout(refreshMapDimensions, 100);
                    setTimeout(refreshMapDimensions, 400);
                    setTimeout(refreshMapDimensions, 1000);
                </script>
            </body>
            </html>
            """

            import streamlit.components.v1 as components
            components.html(html_map_content, height=700)

            # Détail des Liaisons Inter-Provinciales
            if liaisons_interprov:
                with st.expander(f"🌐 Analyse des Liaisons et Proximités Inter-Provinciales ({len(liaisons_interprov)} liaisons ≤ {dist_interprov_max} km)", expanded=True):
                    df_liaisons_display = []
                    for l in liaisons_interprov:
                        t0_a = df_synth.loc[df_synth["Zone de Santé"] == l["zone_a"], "t0"].values
                        t0_b = df_synth.loc[df_synth["Zone de Santé"] == l["zone_b"], "t0"].values
                        t0_a_str = t0_a[0] if len(t0_a) > 0 else "-"
                        t0_b_str = t0_b[0] if len(t0_b) > 0 else "-"
                        df_liaisons_display.append({
                            "Province A": l["prov_a"],
                            "Zone de Santé A": l["zone_a"],
                            "Infrastructure A": l["infra_a"],
                            "Atteinte (A)": t0_a_str,
                            "Distance": f"{l['dist_km']} km",
                            "Province B (Voisine)": l["prov_b"],
                            "Zone de Santé B": l["zone_b"],
                            "Infrastructure B": l["infra_b"],
                            "Atteinte (B)": t0_b_str
                        })

                    st.dataframe(pd.DataFrame(df_liaisons_display), use_container_width=True, height=280)



        with tab_sensibilite:
            st.subheader("Matrice d'Analyse de Sensibilité Provinciale")

            sim_foyers = sim_data.get("simulations_foyers", [sim_data])
            nb_foyers = len(sim_foyers)
            total_zones = sim_data.get("total_zones_province", len(sim_data["df_synth"]))
            df_croise_moyen = sim_data.get("df_croise_moyen")
            if df_croise_moyen is None:
                df_croise_moyen = generer_tableau_croise_seir(sim_data, pas_jours=10, pas_taux=0.05, format_cellule="seir")
            # Options d'affichage interactif
            options_vue = [f"Tableau Moyen de toute la Province ({nb_foyers} foyers aléatoires)"]
            for idx_f, sim_f in enumerate(sim_foyers):
                options_vue.append(f"Foyer {idx_f+1} : {sim_f['zone_depart']} ({sim_f['infra_depart']})")

            col_sel1, col_sel2 = st.columns([2.5, 1])
            with col_sel1:
                vue_choisie = st.selectbox(
                    "Vue du tableau d'analyse de sensibilité :",
                    options=options_vue,
                    index=0,
                    help="Basculez entre la moyenne provinciale agrégée et les tableaux détaillés de chaque foyer individuel."
                )

            if vue_choisie == options_vue[0]:
                df_croise_affiche = df_croise_moyen
                titre_tab = f"Analyse de Sensibilité - Moyenne Provinciale ({sim_data['province']})"
                foyer_desc = f"Moyenne agrégée sur les <b>{nb_foyers}</b> foyers tirés au sort"
            else:
                idx_choisi = options_vue.index(vue_choisie) - 1
                sim_choisie = sim_foyers[idx_choisi]
                df_croise_affiche = generer_tableau_croise_seir(sim_choisie, pas_jours=10, pas_taux=0.05, format_cellule="seir")
                titre_tab = f"Analyse de Sensibilité - Foyer {idx_choisi+1} ({sim_choisie['zone_depart']})"
                foyer_desc = f"Zone de santé : <b>{sim_choisie['zone_depart']}</b> (<i>{sim_choisie['infra_depart']}</i>)"

            # Rendu direct de la Matrice Stylisée
            html_table = generer_html_tableau_croise(df_croise_affiche, sim_data, titre_foyer=titre_tab, info_foyer=foyer_desc)
            st.markdown(html_table, unsafe_allow_html=True)

            if vue_choisie == options_vue[0]:
                images_sensibilite = generer_images_sensibilite_provinciale(
                    df_sensibilite=sim_data.get("df_sensibilite_moyenne"),
                    nom_province=sim_data["province"],
                    nom_maladie=meta["Nom"],
                    modele=sim_data["maladie_meta"].get("Modele", "SIR")
                )
                images_sensibilite_lits = generer_images_sensibilite_lits(
                    df_sensibilite=sim_data.get("df_sensibilite_moyenne"),
                    nom_province=sim_data["province"],
                    nom_maladie=meta["Nom"]
                )
                col_graph_sens, col_graph_lits = st.columns(2)
                with col_graph_sens:
                    if images_sensibilite is not None:
                        st.download_button(
                            label="Télécharger les graphiques de sensibilité",
                            data=images_sensibilite,
                            file_name=f"graphiques_sensibilite_{sim_data['province'].lower().replace(' ', '_')}.zip",
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )
                with col_graph_lits:
                    if images_sensibilite_lits is not None:
                        st.download_button(
                            label="Télécharger les graphiques des lits",
                            data=images_sensibilite_lits,
                            file_name=f"graphiques_lits_sensibilite_{sim_data['province'].lower().replace(' ', '_')}.zip",
                            mime="application/zip",
                            type="primary",
                            use_container_width=True
                        )

            with st.expander(f"Détail des {nb_foyers} zones de santé et infrastructures sélectionnées pour le calcul de la moyenne"):
                liste_foyers_rows = []
                for i_f, s_f in enumerate(sim_foyers):
                    foyer_row = s_f["df_synth"].loc[s_f["df_synth"]["est_foyer"]]
                    pop_val = foyer_row["Population"].values[0] if not foyer_row.empty else "-"
                    lits_val = foyer_row["Cpt Lits"].values[0] if not foyer_row.empty else "-"
                    imax_val = foyer_row["I_max"].values[0] if not foyer_row.empty else "-"
                    liste_foyers_rows.append({
                        "Foyer": f"Foyer {i_f+1}",
                        "Zone de Santé": s_f["zone_depart"],
                        "Infrastructure Référente": s_f["infra_depart"],
                        "Population Zone": f"{pop_val:,}" if isinstance(pop_val, (int, float, np.integer)) else pop_val,
                        "Lits Disponibles Zone": lits_val,
                        "Pic d'Infectés Zone": f"{imax_val:,}" if isinstance(imax_val, (int, float, np.integer)) else imax_val
                    })
                st.dataframe(pd.DataFrame(liste_foyers_rows), use_container_width=True)

            # Calcul des indicateurs d'optimisation capacitaire
            is_vue_moyenne = (vue_choisie == options_vue[0])
            sim_opt_source = sim_data if is_vue_moyenne else sim_foyers[options_vue.index(vue_choisie) - 1]
            res_opt = calculer_indicateurs_optimisation_hospitalisation(
                sim_source=sim_opt_source,
                sim_foyers=sim_foyers if is_vue_moyenne else None,
                is_moyenne=is_vue_moyenne,
                taux_actuel=sim_data.get("maladie_meta", {}).get("TauxHosp", 0.05)
            )

            with st.expander("Tableau Décisionnel d'Optimisation par Palier de Taux (5% à 100%)", expanded=True):
                st.dataframe(
                    res_opt["df_opt"][[
                        "Taux d'Hospitalisation (%)",
                        "Jours de Saturation",
                        "% Durée Saturée",
                        "Déficit Max (Lits)",
                        "Lits Requis au Pic",
                        "Période de Saturation",
                        "Statut Capacitaire"
                    ]],
                    use_container_width=True,
                    height=320
                )

            prov_clean = sim_data["province"].strip().lower().replace(" ", "_")
            maladie_clean = meta["Nom"].strip().lower().replace(" ", "_")

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                buffer_matrice_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_matrice_excel, engine='openpyxl') as writer_matrice:
                    df_croise_moyen.to_excel(writer_matrice, sheet_name='Moyenne_Provinciale')
                buffer_matrice_excel.seek(0)

                st.download_button(
                    label="Télécharger la Matrice Moyenne Provinciale (.xlsx)",
                    data=buffer_matrice_excel,
                    file_name=f"matrice_sensibilite_moyenne_{prov_clean}_{maladie_clean}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

            with col_dl2:
                buffer_multi_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_multi_excel, engine='openpyxl') as writer_multi:
                    df_croise_moyen.to_excel(writer_multi, sheet_name='Moyenne_Provinciale')
                    for i_f, s_f in enumerate(sim_foyers):
                        df_c_f = generer_tableau_croise_seir(s_f, pas_jours=10, pas_taux=0.05, format_cellule="seir")
                        nom_feuille = f"Foyer_{i_f+1}_{s_f['zone_depart'][:15].strip().replace(' ', '_')}"
                        df_c_f.to_excel(writer_multi, sheet_name=nom_feuille[:31])
                buffer_multi_excel.seek(0)

                st.download_button(
                    label="Télécharger le Classeur Multi-Foyers (.xlsx)",
                    data=buffer_multi_excel,
                    file_name=f"classeur_multi_foyers_{prov_clean}_{maladie_clean}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True
                )

        # TAB 4 : Tableaux
        with tab_tables:
            st.subheader("Tableaux de Synthèse & Données Épidémiologiques")

            tab_s1, tab_s2, tab_s3 = st.tabs(["Synthèse par Zone", "Évolution Journalière", "Matrice d'Infection"])

            with tab_s1:
                st.markdown("Synthèse Globale par Zone de Santé")
                df_display = sim_data["df_synth"].drop(columns=["Latitude", "Longitude", "est_foyer"])
                st.dataframe(
                    df_display.style.highlight_max(axis=0, subset=["I_max", "Déficit cpt"], color="#991b1b")
                    .highlight_between(left=1, right=999999, subset=["Déficit cpt"], color="#7f1d1d"),
                    use_container_width=True,
                    height=450
                )

            with tab_s2:
                st.markdown("Évolution Temporelle Détaillée (Format Long)")
                st.dataframe(sim_data["df_long"], use_container_width=True, height=450)

            with tab_s3:
                st.markdown("Matrice des Cas Infectés par Zone (Jour x Zone)")
                st.dataframe(sim_data["df_matrice"], use_container_width=True, height=450)

        # TAB 5 : Export Excel
        with tab_export:
            st.subheader("Exporter les Résultats de Simulation")
            st.write("Téléchargez les rapports complets générés au format Excel (.xlsx), incluant la synthèse par zone, l'évolution journalière, la matrice d'infection et l'analyse de sensibilité multidimensionnelle.")

            df_sensib_export = sim_data.get("df_sensibilite_moyenne")
            if df_sensib_export is None:
                df_sensib_export = generer_matrice_sensibilite(sim_data, pas_jours=10, pas_taux=0.05)

            output_buffer = io.BytesIO()
            engine_to_use = None
            try:
                import openpyxl
                engine_to_use = 'openpyxl'
            except Exception:
                try:
                    import xlsxwriter
                    engine_to_use = 'xlsxwriter'
                except Exception:
                    engine_to_use = None

            if engine_to_use:
                writer = pd.ExcelWriter(output_buffer, engine=engine_to_use)
            else:
                writer = pd.ExcelWriter(output_buffer)

            with writer:
                df_synth_export = sim_data["df_synth"].drop(columns=["Latitude", "Longitude", "est_foyer"], errors='ignore')
                df_synth_export.to_excel(writer, sheet_name='Synthèse_Zones', index=False)
                sim_data["df_long"].to_excel(writer, sheet_name='Évolution_Journalière_Long', index=False)
                sim_data["df_matrice"].to_excel(writer, sheet_name='Infectés_Par_Zone', index=False)
                df_sensib_export.to_excel(writer, sheet_name='Analyse_Sensibilité_Moyenne', index=False)
                
                # Ajout de l'analyse d'optimisation
                res_opt_exp = calculer_indicateurs_optimisation_hospitalisation(
                    sim_source=sim_data,
                    sim_foyers=sim_data.get("simulations_foyers"),
                    is_moyenne=True,
                    taux_actuel=sim_data.get("maladie_meta", {}).get("TauxHosp", 0.05)
                )
                res_opt_exp["df_opt"].to_excel(writer, sheet_name='Optimisation_Capacite', index=False)

            output_buffer.seek(0)

            prov_clean = sim_data["province"].strip().lower().replace(" ", "_")
            maladie_clean = meta["Nom"].strip().lower().replace(" ", "_")
            nom_fichier_excel = f"simulation_{maladie_clean}_{prov_clean}.xlsx"

            col_exp1, col_exp2, col_exp3 = st.columns([1, 2, 1])
            with col_exp2:
                st.download_button(
                    label="Télécharger le Rapport Complet (.xlsx)",
                    data=output_buffer,
                    file_name=nom_fichier_excel,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )




if __name__ == "__main__":
    main()
