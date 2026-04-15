# ImmoPredict SN

**Première plateforme d'intelligence artificielle dédiée au marché immobilier sénégalais.**

ImmoPredict SN agrège en temps réel les annonces immobilières de quatre sources sénégalaises (CoinAfrique, Expat-Dakar, Loger-Dakar, DakarVente), soit plus de 9 500 biens indexés. La plateforme offre un tableau de bord analytique interactif, un estimateur de prix alimenté par le machine learning, un chatbot conversationnel propulsé par Google Gemini, et un système d'alertes personnalisées.

---

## Fonctionnalités

**Scraping multi-sources.** Collecte automatisée des annonces depuis CoinAfrique, Expat-Dakar, Loger-Dakar et DakarVente. Les données sont nettoyées, normalisées et stockées dans PostgreSQL (Neon).

**Dashboard analytique.** Tableau de bord interactif avec 12 graphiques Plotly (distribution des prix, répartition par source, top quartiers, box plots par type, scatter prix/superficie, etc.) et 5 sous-onglets : Vue d'ensemble, Analyse des prix, Sources & Types, Données, Projections.

**Estimation de prix.** Formulaire d'estimation basé sur les données réelles du marché : quartier, type de bien, transaction, superficie et nombre de chambres. Le modèle utilise les médianes par zone pondérées par des multiplicateurs géographiques (Almadies ×3.5, Pikine ×0.7, etc.).

**Chatbot ImmoAI.** Assistant conversationnel propulsé par Google Gemini 2.0 Flash. Répond à toutes les questions (immobilier, culture générale, calculs financiers). Inclut la saisie vocale (Web Speech API), la modification de messages envoyés, et un fallback local intelligent pour les questions immobilières.

**Alertes et notifications.** Système d'alertes automatiques qui notifie les utilisateurs quand un nouveau bien est publié dans leur ville. Les notifications apparaissent dans la cloche de la barre de navigation et peuvent être envoyées par email.

**Espace vendeur.** Les utilisateurs peuvent passer en mode vendeur, publier des annonces avec photos, et gérer leur portefeuille de biens.

**Carte interactive.** Visualisation géographique des annonces sur une carte Leaflet/OpenStreetMap avec filtres et recherche.

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Django 5.x / Python 3.11+ |
| Base de données | PostgreSQL (Neon) |
| Frontend | HTML5, CSS3 (variables custom), JavaScript vanilla |
| Graphiques | Plotly.js 2.27 |
| Chatbot | Google Gemini 2.0 Flash API |
| ML / Estimation | Statistiques + multiplicateurs géographiques |
| Déploiement | Render (Web Service) |
| Stockage fichiers | Render Disk / Cloudinary |

---

## Installation

### Prérequis

- Python 3.11+
- PostgreSQL (ou compte Neon)
- Clé API Google Gemini (gratuite)

### Cloner et installer

```bash
git clone https://github.com/votre-username/immopredict-sn.git
cd immopredict-sn
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Variables d'environnement

Créez un fichier `.env` à la racine du projet :

```env
SECRET_KEY=votre-cle-secrete-django
DATABASE_URL=postgresql://user:password@host:5432/dbname
GEMINI_API_KEY=AIza_votre_cle_gemini
DEBUG=True
```

Pour obtenir une clé Gemini gratuite, rendez-vous sur [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### Migrations et lancement

```bash
python manage.py makemigrations listings
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

---

## Structure du projet

```
immopredict-sn/
├── immobilier_project/        # Configuration Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── immoanalytics_dash/        # App principale
│   ├── views.py               # Vues (auth, pages, API)
│   ├── chart_views.py         # Dashboard + graphiques
│   └── chatbot_gemini.py      # Chatbot Gemini
├── listings/                  # Annonces vendeurs
│   ├── models.py              # UserProfile, Listing, Alert, ContactMessage
│   ├── views.py               # Vente, Location, Profil
│   └── signals.py             # Notifications automatiques
├── properties/                # Données scrapées
│   └── models.py              # CoinAfrique, ExpatDakar, LogerDakar, DakarVente
├── templates/immoanalytics/   # 23 templates HTML
├── static/immoanalytics/      # CSS, JS, images, logo
└── requirements.txt
```

---

## Déploiement sur Render

1. Connectez votre dépôt GitHub à Render.
2. Créez un **Web Service** avec les paramètres suivants :
   - Build Command : `./build.sh`
   - Start Command : `gunicorn immobilier_project.wsgi:application`
3. Ajoutez les variables d'environnement (`DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`).
4. Créez une base PostgreSQL Neon et copiez l'URL de connexion dans `DATABASE_URL`.

---

## Configuration du chatbot

Le chatbot utilise exclusivement l'API Google Gemini. Sans clé API, un mode local répond aux questions immobilières basiques. Avec la clé, le chatbot devient un assistant polyvalent capable de répondre à toute question.

```bash
# Installer le SDK
pip install google-generativeai

# Configurer la clé (local)
export GEMINI_API_KEY="AIza_votre_cle"

# Configurer la clé (Render)
# Dashboard → Environment → GEMINI_API_KEY
```

Quotas gratuits Gemini : 1 500 requêtes/jour, 15 requêtes/minute.

---

## Captures d'écran

| Page d'accueil | Dashboard | Chatbot |
|---|---|---|
| Page de bienvenue avec carrousel d'images et statistiques clés | Tableau de bord avec 12 graphiques interactifs et 5 onglets | Assistant IA avec saisie vocale et modification de messages |

---

## Auteure

**Asma GUEYE** — Étudiante en Licence Mathématiques-Statistiques-Économie, option Data Science, ENSAE Dakar.

---

## Licence

Ce projet est développé dans un cadre académique. Tous droits réservés.
