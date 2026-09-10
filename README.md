# 🦠 Epidemia - Dashboard Épidémiologique & Simulation Spatio-Temporelle (RD Congo)

**Epidemia** est une application web interactive développée sous **Streamlit** conçue pour la modélisation mathématique, la simulation de propagation spatio-temporelle des maladies infectieuses (Choléra, etc.) et l'optimisation des capacités hospitalières à l'échelle provinciale et nationale en **République Démocratique du Congo (RDC)**.

---

## 🌟 Fonctionnalités Clés

1. **Connexion & Introspection MySQL Dynamique** :
   - Connexion sécurisée via SQLAlchemy.
   - Détection automatique des structures d'infrastructures sanitaires et des zones de santé de la province sélectionnée.
2. **Modélisation Épidémiologique Avancée (SIR / SEIR)** :
   - Résolution d'équations différentielles ordinaires (ODE) avec `scipy.integrate.odeint`.
   - Gestion des compartiments **Susceptibles (S)**, **Exposés (E)**, **Infectés (I)** et **Rétablis (R)** selon les paramètres cliniques spécifiques de chaque maladie ($R_0$, durée $D$, période d'incubation $E$).
3. **Modèle de Mobilité Spatiale Gravitaire** :
   - Calcul des flux inter-infrastructures basé sur la distance orthodromique (formule de Haversine) et la taille démographique des zones de santé.
   - Simulation multi-foyers (aléatoire ou ciblée).
4. **Analyse de Sensibilité Multidimensionnelle & Arbitrage Hospitalier** :
   - Simulation croisée faisant varier les paliers temporels et le **taux d'hospitalisation** (de 5% à 100%).
   - Évaluation de l'impact clinique sur l'accélération de la guérison ($\gamma_{eff}$), la réduction du $R_0$ effectif et la minimisation des jours de saturation capacitaire.
5. **Visualisations & Cartographie Interactive** :
   - Courbes dynamiques interactives (Plotly) de la dynamique globale et par zone de santé.
   - Carte de propagation temporelle avec curseur de temps, marqueurs dynamiques proportionnels aux cas actifs et alertes de saturation.
6. **Optimisation des Capacités & Tableaux de Synthèse** :
   - Calcul des pics épidémiologiques, des lits requis vs lits existants, et des déficits cumulés en lits d'hôpitaux.

---

## 🛠️ Stack Technique

* **Interface Web** : Streamlit (`st.set_page_config`, composants natifs, CSS adaptatif Mode Clair/Sombre).
* **Calculs Mathématiques & Scientifiques** : `NumPy`, `SciPy` (`odeint`).
* **Gestion des Données** : `Pandas`, `SQLAlchemy`, `PyMySQL`.
* **Visualisations Graphiques** : `Plotly` (`graph_objects`, `express`).
* **Cartographie Spatiale** : Intégration HTML/JS Leaflet personnalisée avec rendu dynamique.

---

## 📋 Prérequis & Configuration de la Base de Données

L'application nécessite une base de données MySQL structurée contenant au minimum les tables suivantes :
* `zonesante` : Informations démographiques et géographiques des zones de santé (avec `idZone`, `NomZone`, `province`, `population_2026`, `capacite_totale`).
* `infrastructures` : Structures de santé rattachées aux zones (`idZone`, nom de l'infrastructure, `latitude`, `longitude`).
* `maladie` : Paramètres épidémiologiques des pathologies (`NomMaladie`, `Ro`, `D`, `E`, `modele`, `TauxHospitalisation`).

---

## 🚀 Installation & Exécution

1. **Cloner le dépôt** :
   ```bash
   git clone https://github.com/votre-nom/epidemia-rdc.git
   cd epidemia-rdc
   ```

2. **Installer les dépendances Python** :
   ```bash
   pip install -r requirements.txt
   ```
   *(Dépendances principales : `streamlit`, `pandas`, `numpy`, `scipy`, `sqlalchemy`, `pymysql`, `plotly`)*

3. **Configurer l'accès MySQL** :
   Lancer l'application et renseigner vos identifiants MySQL dans la barre latérale (Sidebar) de l'application Streamlit (Hôte, Port, Utilisateur, Mot de passe, Nom de la base).

4. **Lancer l'application Streamlit** :
   ```bash
   streamlit run epidemiaTH.py
   ```

---

## 📖 Utilisation de l'Application

1. Barre Latérale (Sidebar) :
   - Saisissez vos paramètres de connexion MySQL.
   - Sélectionnez la **Province** cible en RDC.
   - Choisissez le mode d'épicentre (**Aléatoire** avec option de graine / **Personnalisé**).
   - Sélectionnez la **Maladie** (ex: Choléra).
   - Ajustez le **Taux d'hospitalisation** et la **Durée de simulation** (en jours).
   - Cliquez sur **Lancer la Simulation**.
2. Exploration des Onglets:
   - **Courbes Épidémiologiques** : Visualisez l'évolution globale de la province et zoomez sur chaque zone de santé.
   - **Carte Interactive** : Suivez jour par jour la propagation de l'épidémie sur la carte géographique de la province grâce au curseur temporel et l'animation de lecture.
   - **Analyse de Sensibilité** : Analysez la matrice croisée et l'arbitrage entre taux d'hospitalisation et saturation des lits.
   - **Synthèse & Données Détaillées** : Consultez les tableaux agrégés des pics et des déficits capacitaires.
   - **Exportation Excel** : Exportez les résultats de simulation.

---
