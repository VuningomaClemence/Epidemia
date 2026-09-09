import io
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
        margin-bottom: 0.5rem;
    }
    .metric-value {
        color: var(--card-text, var(--text-color));
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-sub {
        color: #0284c7;
        font-size: 0.85rem;
        margin-top: 0.4rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


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


def simuler_epidemic_streamlit(engine, df_maladies, nom_province, nom_infra_depart="ALEATOIRE", nom_maladie_saisie="Choléra", duree_jours=100, taux_hospitalisation=None, theta=1e-5, gamma_dist=2.0, seed_epicentre=None):
    """Effectue la simulation SIR / SEIR spatio-temporelle pour plusieurs foyers aléatoires (moitié ou moitié+1 zones) et agrège les résultats."""
    
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

    # 2. Zones et Infrastructures
    colonne_nom_infra = trouver_nom_colonne_infra(engine)
    query_zones_infra = text(f"""
        SELECT 
            z.idZone,
            z.NomZone AS nomZone,
            z.province,
            z.population_2026,
            COALESCE(z.capacite_totale, 50) AS lits_reels,
            i.{colonne_nom_infra} AS nom_infra_ref,
            i.latitude AS latitude_infra,
            i.longitude AS longitude_infra
        FROM zonesante z
        JOIN infrastructures i ON z.idZone = i.idZone
        WHERE LOWER(TRIM(z.province)) = LOWER(TRIM(:prov))
        GROUP BY z.idZone, z.NomZone, z.province, z.population_2026, z.capacite_totale
    """)
    
    with engine.connect() as conn:
        df_zones_p = pd.read_sql(query_zones_infra, conn, params={"prov": nom_province})

    df_zones_p['latitude_infra'] = pd.to_numeric(df_zones_p['latitude_infra'], errors='coerce')
    df_zones_p['longitude_infra'] = pd.to_numeric(df_zones_p['longitude_infra'], errors='coerce')
    df_zones_p = df_zones_p.dropna(subset=['latitude_infra', 'longitude_infra']).reset_index(drop=True)

    if df_zones_p.empty:
        return None, f"Aucune zone de santé avec infrastructure géolocalisée dans la province '{nom_province}'."

    K = len(df_zones_p)
    N_vec = df_zones_p['population_2026'].values
    M = generer_matrice_mobilite_infrastructures(df_zones_p, theta=theta, gamma_dist=gamma_dist)
    t_total = np.linspace(1, duree_jours, duree_jours)
    est_seir = (modele_type == 'SEIR' and E_base > 0)

    # 3. Calcul du nombre de zones de santé à sélectionner :
    # Égal à la moitié du nombre des zones de santé de la province, ou moitié plus un si c'est impair
    nb_foyers = (K // 2) + 1 if (K % 2 != 0) else (K // 2)
    nb_foyers = max(1, min(K, nb_foyers))

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
        # Tirage aléatoire sans remise de nb_foyers zones distinctes
        indices_foyers = rng.choice(K, size=nb_foyers, replace=False).tolist()
    else:
        # Recherche de l'infrastructure saisie
        saisie_epuree = infra_saisie.lower()
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
                idx_manuel = int(rng.randint(0, K))
        else:
            idx_manuel = int(rng.randint(0, K))

        autres_indices = [i for i in range(K) if i != idx_manuel]
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
    - L'impact clinique de l'hospitalisation sur le taux de guérison (gamma_eff) et la durée moyenne de maladie (D_eff)
    - La réduction du R0 effectif et l'accélération de l'extinction épidémique (minimisation des jours)
    - La durée totale de l'épidémie (en jours jusqu'à extinction sous seuil)
    - Le pic d'infectés et les lits requis
    - Le nombre de jours de saturation (Lits Requis > Lits Existants)
    - Le pic de déficit en lits
    - L'identification du taux d'hospitalisation optimal acceptable (minimisant les jours avec 0 jour de saturation).
    """
    df_synth = sim_source.get("df_synth")
    lits_existants = int(df_synth["Cpt Lits"].sum()) if (df_synth is not None and "Cpt Lits" in df_synth.columns) else 0

    meta = sim_source.get("maladie_meta", {})
    D_base = float(meta.get("D", 10.0)) if pd.notna(meta.get("D")) and float(meta.get("D", 0)) > 0 else 10.0
    R0_base = float(meta.get("Ro", 2.0)) if pd.notna(meta.get("Ro")) and float(meta.get("Ro", 0)) > 0 else 2.0
    gamma_base = 1.0 / D_base
    alpha_soins = 0.8  # Facteur d'accélération clinique des soins hospitaliers (+80% au taux de 100%)

    if is_moyenne and sim_foyers:
        sim_daily_I = []
        for sim in sim_foyers:
            d_j = sim["df_long"].groupby("Jour")["Infectés (I)"].sum()
            sim_daily_I.append(d_j)
        df_daily_all = pd.concat(sim_daily_I, axis=1)
        serie_I = df_daily_all.mean(axis=1)
    else:
        serie_I = sim_source["df_long"].groupby("Jour")["Infectés (I)"].sum()

    I_max_base = float(serie_I.max()) if not serie_I.empty else 0.0
    duree_sim = int(serie_I.index.max()) if not serie_I.empty else 100
    t_vals = serie_I.index.values

    taux_hosp_liste = np.round(np.arange(0.05, 1.01, 0.05), 2)
    lignes_opt = []
    meilleur_taux_acceptable = 5

    for taux in taux_hosp_liste:
        taux_pct = int(round(taux * 100))
        
        # 1. Impact sur le taux de guérison et la durée de contagiosité
        gamma_eff = gamma_base * (1.0 + alpha_soins * taux)
        D_eff = round(1.0 / gamma_eff, 1)
        R_eff = round(R0_base / (1.0 + alpha_soins * taux), 2)
        
        # 2. Ajustement de la dynamique temporelle (accélération de la guérison et réduction des jours)
        ratio_acceleration = gamma_base / gamma_eff
        t_scaled = t_vals / ratio_acceleration
        I_tau = np.interp(t_scaled, t_vals, serie_I.values, right=0)
        
        # 3. Calcul de la durée totale de l'épidémie (jours jusqu'à extinction)
        seuil_extinction = max(1.0, 0.005 * I_max_base)
        jours_actifs = np.where(I_tau >= seuil_extinction)[0]
        if len(jours_actifs) > 0:
            duree_epidemie_jours = int(t_vals[jours_actifs[-1]])
        else:
            duree_epidemie_jours = duree_sim

        I_max_tau = float(np.max(I_tau))
        lits_req_serie = np.round(I_tau * taux)
        deficit_serie = np.maximum(0, lits_req_serie - lits_existants)
        sature_serie = lits_req_serie > lits_existants
        
        jours_sat = int(np.sum(sature_serie))
        pct_sat = round((jours_sat / max(1, duree_sim)) * 100, 1)
        def_max = int(np.max(deficit_serie))
        lits_pic = int(round(I_max_tau * taux))
        
        if jours_sat == 0:
            statut = "Acceptable (0j saturation)"
            if taux_pct >= meilleur_taux_acceptable:
                meilleur_taux_acceptable = taux_pct
        elif pct_sat <= 15:
            statut = "Tension Modérée"
        else:
            statut = "Saturation Critique"
            
        lignes_opt.append({
            "Taux d'Hospitalisation (%)": f"{taux_pct}%",
            "Taux_Num": taux_pct,
            "Taux_Val": taux,
            "Durée Guérison (D)": f"{D_eff} j",
            "R0 Effectif": R_eff,
            "Durée Épidémie": f"{duree_epidemie_jours} jours",
            "Durée_Num": duree_epidemie_jours,
            "Pic Infectés (I_max)": int(round(I_max_tau)),
            "Lits Requis au Pic": lits_pic,
            "Jours de Saturation": jours_sat,
            "Déficit Max (Lits)": def_max,
            "Statut d'Acceptabilité": statut
        })

    df_opt = pd.DataFrame(lignes_opt)

    # Informations pour le taux optimal acceptable
    rows_acc = df_opt[df_opt["Taux_Num"] == meilleur_taux_acceptable]
    row_acceptable = rows_acc.iloc[0] if not rows_acc.empty else df_opt.iloc[0]
    row_min = df_opt.iloc[0]
    duree_au_taux_min = row_min["Durée_Num"]
    duree_au_taux_acceptable = row_acceptable["Durée_Num"]
    gain_jours = max(0, duree_au_taux_min - duree_au_taux_acceptable)

    # Calcul pour le taux actuel de la simulation
    taux_actuel_float = float(taux_actuel) if taux_actuel <= 1.0 else float(taux_actuel) / 100.0
    taux_actuel_pct = int(round(taux_actuel_float * 100))
    idx_closest = (np.abs(df_opt["Taux_Num"] - taux_actuel_pct)).argmin()
    row_actuel = df_opt.iloc[idx_closest]

    return {
        "df_opt": df_opt,
        "taux_optimal_acceptable_pct": meilleur_taux_acceptable,
        "duree_au_taux_acceptable": duree_au_taux_acceptable,
        "duree_au_taux_min": duree_au_taux_min,
        "gain_jours": gain_jours,
        "d_eff_acceptable": row_acceptable["Durée Guérison (D)"],
        "r0_eff_acceptable": row_acceptable["R0 Effectif"],
        "taux_actuel_pct": taux_actuel_pct,
        "jours_sat_actuel": row_actuel["Jours de Saturation"],
        "def_max_actuel": row_actuel["Déficit Max (Lits)"],
        "duree_epidemie_actuel": row_actuel["Durée Épidémie"],
        "lits_existants": lits_existants,
        "D_base": D_base,
        "R0_base": R0_base
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
                    seed_epicentre=seed_val
                )
                if err:
                    st.error(err)
                else:
                    st.session_state["sim_data"] = res

    sim_data = st.session_state.get("sim_data")

    # Affichage du Dashboard
    if sim_data:
        df_synth = sim_data["df_synth"]
        df_prov_daily = sim_data["df_prov_daily"]
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
                col_left, col_right = st.columns([2, 1.25])

                with col_left:
                    fig_prov = go.Figure()
                    fig_prov.add_trace(go.Scatter(
                        x=df_prov_daily["Jour"], y=df_prov_daily["Susceptibles (S)"],
                        mode='lines', name='Susceptibles (S)', line=dict(color='#38bdf8', width=2.5)
                    ))
                    if "Exposés (E)" in df_prov_daily.columns:
                        fig_prov.add_trace(go.Scatter(
                            x=df_prov_daily["Jour"], y=df_prov_daily["Exposés (E)"],
                            mode='lines', name='Exposés (E)', line=dict(color='#f59e0b', width=2.5)
                        ))
                    fig_prov.add_trace(go.Scatter(
                        x=df_prov_daily["Jour"], y=df_prov_daily["Infectés (I)"],
                        mode='lines', name='Infectés (I)', line=dict(color='#ef4444', width=3)
                    ))
                    fig_prov.add_trace(go.Scatter(
                        x=df_prov_daily["Jour"], y=df_prov_daily["Rétablis (R)"],
                        mode='lines', name='Rétablis (R)', line=dict(color='#10b981', width=2.5)
                    ))

                    fig_prov.update_layout(
                        title=f"Dynamique Globale - Province de {sim_data['province']}",
                        xaxis_title="Jour de Simulation",
                        yaxis_title="Nombre d'Individus",
                        hovermode="x unified",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=480,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )

                    st.plotly_chart(fig_prov, use_container_width=True)

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
                        xaxis_title="Jour",
                        yaxis_title="Cas",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=415
                    )

                    st.plotly_chart(fig_zone, use_container_width=True)

                st.markdown("---")
                st.subheader("Comparatif de la Capacité Hospitalière par Zone")

                fig_hosp = go.Figure()
                fig_hosp.add_trace(go.Bar(
                    x=df_synth["Zone de Santé"], y=df_synth["Cpt Lits"],
                    name="Lits Disponibles", marker_color="#3b82f6"
                ))
                fig_hosp.add_trace(go.Bar(
                    x=df_synth["Zone de Santé"], y=df_synth["CapRequisPic"],
                    name="Lits Requis au Pic", marker_color="#f43f5e"
                ))

                st.plotly_chart(fig_hosp, use_container_width=True)

            else:
                st.info("Plotly n'est pas disponible. Affichage natif Streamlit.")
                df_chart_data = df_prov_daily.set_index("Jour")
                st.line_chart(df_chart_data[["Susceptibles (S)", "Infectés (I)", "Rétablis (R)"]])

        # TAB 2 : Carte Interactive & Simulation Spatio-Temporelle
        with tab_carte:
            st.subheader(f"Carte de Propagation Épidémique - Province de {sim_data['province']}")

            import json

            center_lat = float(df_synth["Latitude"].dropna().mean()) if (not df_synth.empty and pd.notna(df_synth["Latitude"].mean())) else -4.03
            center_lon = float(df_synth["Longitude"].dropna().mean()) if (not df_synth.empty and pd.notna(df_synth["Longitude"].mean())) else 21.75
            total_zones = len(df_synth)
            sim_duree = int(sim_data["df_long"]["Jour"].max()) if not sim_data["df_long"].empty else duree_jours

            est_seir_sim = (meta.get("Modele") == "SEIR")
            daily_data_dict = {}

            for j_day in range(1, sim_duree + 1):
                df_day_long = sim_data["df_long"][sim_data["df_long"]["Jour"] == j_day]
                if df_day_long.empty:
                    df_day_merged = df_synth.copy()
                    df_day_merged["Jour"] = j_day
                    df_day_merged["Infectés (I)"] = 0
                    df_day_merged["Lits Occupés"] = 0
                    df_day_merged["Susceptibles (S)"] = df_day_merged["Population"]
                    df_day_merged["Rétablis (R)"] = 0
                    if est_seir_sim:
                        df_day_merged["Exposés (E)"] = 0
                else:
                    df_day_merged = pd.merge(df_synth, df_day_long, on="Zone de Santé", how="left")

                inf_tot_day = int(df_day_merged["Infectés (I)"].fillna(0).sum())
                lits_occ_day = int(df_day_merged["Lits Occupés"].fillna(0).sum())
                zones_active_day = int((df_day_merged["Infectés (I)"].fillna(0) > 0).sum())
                exp_tot_day = int(df_day_merged["Exposés (E)"].fillna(0).sum()) if est_seir_sim and "Exposés (E)" in df_day_merged.columns else 0
                ret_tot_day = int(df_day_merged["Rétablis (R)"].fillna(0).sum())

                day_markers = []

                for idx, row in df_day_merged.iterrows():
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
                        badge_icon = "🛡️"
                        status_title = f"Zone Rétablie (Épidémie éteinte)<br>({r_j}rétablies)"
                        radius_size = 7
                    elif est_foyer and inf_j > 0:
                        category = "foyer"
                        color_hex = "#dc2626"
                        badge_icon = "★"
                        hosp_txt = f"Saturation Hospitalière (Déficit: {defic_j} lits)" if defic_j > 0 else "Capacité hospitalière suffisante"
                        status_title = f"Épicentre / Foyer Initial ({inf_j:,} cas) - {hosp_txt}"
                        radius_size = int(max(10, min(42, int(np.sqrt(max(1, inf_j)) * 0.5))))
                    elif defic_j > 0:
                        category = "saturation"
                        color_hex = "#ef4444"
                        badge_icon = "✚"
                        status_title = f"Zone Active - Saturation Hospitalière ({inf_j:,} cas<br>Déficit: {defic_j} lits)"
                        radius_size = int(max(8, min(45, int(np.sqrt(inf_j) * 0.5))))
                    else:
                        category = "active"
                        color_hex = "#f97316"
                        badge_icon = "▲"
                        status_title = f"Zone Active ({inf_j:,} cas | Capacité OK)"
                        radius_size = int(max(7, min(45, int(np.sqrt(inf_j) * 0.5))))

                    exp_row_html = f"<tr><td><b>Exposés (E) :</b></td><td><b style='color: #a855f7;'>{exp_j:,}</b></td></tr>" if est_seir_sim else ""

                    popup_html = f"""
                    <div style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; min-width: 230px; line-height: 1.4;">
                        <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid {color_hex}; padding-bottom: 5px; margin-bottom: 6px;">
                            <h4 style="margin: 0; color: #0f172a; font-size: 14px; font-weight: 700;">{nom_z}</h4>
                            <span style="background: {color_hex}; color: white; padding: 2px 7px; border-radius: 10px; font-size: 10px; font-weight: 600;">Jour {j_day}</span>
                        </div>
                        <p style="font-size: 11px; margin: 0 0 5px 0; color: #64748b;"><b>Infra ref :</b> {infra}</p>
                        <p style="font-size: 11px; margin: 0 0 6px 0; color: #334155;"><b>Statut :</b> {status_title}</p>
                        <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Population :</b></td><td style="text-align: right;">{pop:,}</td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Susceptibles (S) :</b></td><td style="text-align: right; color: #0284c7;">{s_j:,}</td></tr>
                            {exp_row_html}
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Infectés Actifs (I) :</b></td><td style="text-align: right;"><b style="color: {'#2563eb' if inf_j==0 else '#ef4444'};">{inf_j:,}</b></td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Rétablis (R) :</b></td><td style="text-align: right; color: #10b981;">{r_j:,}</td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Lits Occupés :</b></td><td style="text-align: right;">{lits_req_j:,} / {lits:,}</td></tr>
                            <tr style="border-top: 1px solid #f1f5f9;"><td><b>Déficit Lits :</b></td><td style="text-align: right;"><b style="color: {'#ef4444' if defic_j > 0 else '#10b981'};">{defic_j}</b></td></tr>
                        </table>
                    </div>
                    """

                    day_markers.append({
                        "lat": lat,
                        "lon": lon,
                        "nom_z": nom_z,
                        "status_txt": f"{nom_z} : {status_title}",
                        "category": category,
                        "color_hex": color_hex,
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
            for _, r in df_synth.iterrows():
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
                        max-width: 260px;
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
                    <div class="map-legend-box">
                        <div class="legend-title">Légende Épidémiologique</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #10b981;"></span> Saine (Non touchée)</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #dc2626; border: 2px solid #fff; box-shadow: 0 0 4px red;"></span> ★ Foyer Initial / Épicentre</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #ef4444;"></span> Active (Saturation Lits)</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #f97316;"></span> Active (Capacité OK)</div>
                        <div class="legend-item"><span class="legend-dot" style="background: #3b82f6;"></span> Rétablie (0 cas actif)</div>
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

                    function createPinIcon(d) {{
                        const isEpicenter = (d.category === 'foyer');
                        const isSaturated = (d.category === 'saturation');
                        const glowClass = (isEpicenter || isSaturated) ? 'radar-active' : '';
                        
                        const pinHtml = `
                            <div class="custom-svg-pin ${{glowClass}}" style="width: 32px; height: 32px; position: relative;">
                                <svg width="32" height="32" viewBox="0 0 32 32" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));">
                                    <path d="M16 2C10.48 2 6 6.48 6 12c0 7.5 10 18 10 18s10-10.5 10-18c0-5.52-4.48-10-10-10z" fill="${{d.color_hex}}" stroke="#ffffff" stroke-width="1.8"/>
                                    <circle cx="16" cy="12" r="5.5" fill="#ffffff" />
                                    <text x="16" y="15" text-anchor="middle" font-size="8" font-family="sans-serif" font-weight="bold" fill="${{d.color_hex}}">${{d.badge_icon}}</text>
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
                                        fillColor: d.color_hex,
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
            components.html(html_map_content, height=760)

        # TAB 3 : Analyse de Sensibilité (Matrice Stylisée SEIR)
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

            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                st.download_button(
                    label="Télécharger le Rapport Complet (.xlsx)",
                    data=output_buffer,
                    file_name=nom_fichier_excel,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            with col_exp2:
                buffer_sensib_full = io.BytesIO()
                with pd.ExcelWriter(buffer_sensib_full, engine=engine_to_use if engine_to_use else 'openpyxl') as writer_sensib:
                    df_sensib_export.to_excel(writer_sensib, sheet_name='Analyse_Sensibilité_Moyenne', index=False)
                buffer_sensib_full.seek(0)
                st.download_button(
                    label="Télécharger l'Analyse de Sensibilité Moyenne (.xlsx)",
                    data=buffer_sensib_full,
                    file_name=f"sensibilite_moyenne_{maladie_clean}_{prov_clean}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
