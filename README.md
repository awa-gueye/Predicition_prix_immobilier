# 📊 Projet de scraping immobilier – Sénégal

Récupération automatique et centralisée des annonces **vente / location** publiées sur les principales plateformes sénégalaises :

- [Coin-Afrique](https://sn.coinafrique.com)
- [Expat-Dakar](https://www.expat-dakar.com)
- [Loger-Dakar](https://www.loger-dakar.com)

---

## 🚀 Fonctionnalités

| Site | Spider | Pipeline dédié | Table PostgreSQL | Statut |
|------|--------|----------------|------------------|--------|
| Coin-Afrique | `coinafrique_html` | `PostgreSQLPipeline` | `properties` | ✅ |
| Expat-Dakar | `expat_dakar_paginated` | `ExpatDakarPostgreSQLPipeline` | `expat_dakar_properties` | ✅ |
| Loger-Dakar | `loger_dakar` | `LogerDakarPostgreSQLPipeline` | `loger_dakar_properties` | ✅ |

- **Pagination automatique** (bouton « Suivant »)
- **Dé-duplication** par hash MD5 de l’URL
- **Validation** des champs obligatoires (prix, titre, etc.)
- **Normalisation** des données (prix CFA → int, « 3 Ch » → 3, etc.)

---

## 📦 Stack technique

| Couche | Techno |
|--------|--------|
| Crawling | [Scrapy](https://scrapy.org) 2.11 |
| BDD | PostgreSQL 15 |
| Langage | Python 3.10+ |
| ORM | *(aucun – SQL brut via psycopg2)* |

---

## ⚙️ Installation rapide

```bash
# 1. Cloner
git clone https://github.com/ba2664890/Stage_ANSD.git
cd Stage_ANSD

# 2. Environnement virtuel
python -m venv env
source env/bin/activate          # Linux / macOS
# env\Scripts\activate           # Windows

# 3. Dépendances
pip install -r requirements.txt   # scrapy psycopg2-binary itemloaders
