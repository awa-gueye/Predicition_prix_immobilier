"""
properties/ml/predict.py

Interface Django ↔ modèle ML entraîné dans le Notebook 4.
Le modèle est sauvegardé sous forme de dict :
  {
    "pipeline":             <sklearn Pipeline>,
    "best_model_name":      str,
    "features":             num_feats + cat_feats,
    "numeric_features":     [...],
    "categorical_features": [...],
    "metrics":              {...},
  }

Features numériques (44) + catégorielles (2) = 46 features au total.
Appelé depuis immoanalytics_dash/views.py → _estimate()
"""
import os
import math
import numpy as np
import pandas as pd

ML_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Cache en mémoire ──────────────────────────────────────────────────────────
_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        import joblib
        path = os.path.join(ML_DIR, "model.pkl")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Modèle introuvable : {path}\n"
                "Exécutez le Notebook 4 pour générer model.pkl"
            )
        _bundle = joblib.load(path)
    return _bundle


# ── Coordonnées GPS approximatives par quartier ───────────────────────────────
# (latitude, longitude) — utilisées pour calculer les distances aux POI
CITY_GPS = {
    "almadies":     (14.745, -17.510), "ngor":          (14.749, -17.514),
    "ouakam":       (14.724, -17.494), "mermoz":        (14.710, -17.475),
    "plateau":      (14.693, -17.447), "fann":          (14.696, -17.460),
    "yoff":         (14.758, -17.490), "pikine":        (14.755, -17.395),
    "guediawaye":   (14.778, -17.393), "rufisque":      (14.716, -17.274),
    "liberte":      (14.715, -17.463), "hlm":           (14.713, -17.459),
    "sicap":        (14.712, -17.462), "grand yoff":    (14.736, -17.467),
    "keur massar":  (14.765, -17.340), "medina":        (14.695, -17.456),
    "parcelles":    (14.748, -17.451), "sacre coeur":   (14.720, -17.461),
    "point e":      (14.694, -17.460), "vdn":           (14.730, -17.470),
    "hann":         (14.720, -17.430), "thies":         (14.791, -16.926),
    "mbour":        (14.368, -16.965), "saly":          (14.454, -17.012),
    "dakar":        (14.693, -17.447), "default":       (14.710, -17.470),
}

# ── POI (Points d'intérêt) ────────────────────────────────────────────────────
POI = {
    "mer":      (14.693, -17.459),  # Corniche de Dakar
    "centre":   (14.693, -17.447),  # Plateau (centre-ville)
    "aeroport": (14.741, -17.490),  # Aéroport Léopold Sédar Senghor
    "parc":     (14.700, -17.458),  # Parc de Hann
    "ucad":     (14.692, -17.464),  # Université Cheikh Anta Diop
    "vdn":      (14.730, -17.470),  # VDN
    "port":     (14.672, -17.427),  # Port de Dakar
    "corniche": (14.710, -17.470),  # Corniche Ouest
}

# ── Quartiers premium ─────────────────────────────────────────────────────────
PREMIUM_ZONES = {
    "almadies", "ngor", "mermoz", "fann", "plateau", "sacre coeur",
    "point e", "corniche", "yoff", "saly",
}


def _haversine(lat1, lon1, lat2, lon2) -> float:
    """Distance en km entre deux points GPS."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda= math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _get_gps(city: str):
    """Retourne les coordonnées GPS d'un quartier."""
    if not city:
        return CITY_GPS["default"]
    key = city.lower().strip()
    # Recherche exacte
    if key in CITY_GPS:
        return CITY_GPS[key]
    # Recherche partielle
    for k, v in CITY_GPS.items():
        if k in key or key in k:
            return v
    return CITY_GPS["default"]


def _nlp_features(description: str = "", title: str = "") -> dict:
    """Extrait les features NLP depuis description et titre."""
    text = (str(description or "") + " " + str(title or "")).lower()
    return {
        "has_standing":      int(any(w in text for w in ["standing","grand standing","luxe","haut standing"])),
        "has_neuf":          int(any(w in text for w in ["neuf","nouvelle construction","tout neuf"])),
        "has_renove":        int(any(w in text for w in ["renov","refait","refection","modernise"])),
        "has_piscine":       int(any(w in text for w in ["piscine","pool","swimming"])),
        "has_meuble":        int(any(w in text for w in ["meuble","equipe","amenage"])),
        "has_climatise":     int(any(w in text for w in ["clim","climatis","air conditionne"])),
        "has_ascenseur":     int(any(w in text for w in ["ascenseur","elevator","lift"])),
        "has_cuisine_amer":  int(any(w in text for w in ["cuisine americaine","cuisine integree","open kitchen"])),
        "has_parking":       int(any(w in text for w in ["parking","garage","carport","voiture"])),
        "has_jardin":        int(any(w in text for w in ["jardin","garden","verdure","espace vert"])),
        "has_balcon":        int(any(w in text for w in ["balcon","terrasse","loggia"])),
        "has_gardiennage":   int(any(w in text for w in ["gardien","vigile","securite","gardiennage"])),
        "has_groupe_elec":   int(any(w in text for w in ["groupe electrogene","generateur","groupe elec"])),
        "has_vue_mer":       int(any(w in text for w in ["vue mer","face mer","bord de mer","ocean"])),
        "has_concierge":     int(any(w in text for w in ["concierge","reception","accueil"])),
        "has_digicode":      int(any(w in text for w in ["digicode","interphone","visiophone","badge"])),
        "has_titre_foncier": int(any(w in text for w in ["titre foncier","tf","foncier","regularise"])),
        "has_viabilise":     int(any(w in text for w in ["viabilise","eau electricite","borne"])),
        "has_invest":        int(any(w in text for w in ["investissement","rendement","rentable","locatif"])),
    }


def _build_features(city, property_type, surface_area, bedrooms, bathrooms,
                    garage=0, source="coinafrique",
                    description="", title="",
                    city_prix_m2_median=None) -> pd.DataFrame:
    """
    Construit le DataFrame de features à partir des inputs utilisateur.
    Reconstitue les 46 features du modèle.
    """
    # GPS
    lat, lon = _get_gps(city)
    city_key = (city or "dakar").lower().strip()
    is_premium = int(any(p in city_key for p in PREMIUM_ZONES))

    # Distances aux POI
    dists = {f"dist_{k}": _haversine(lat, lon, *v) for k, v in POI.items()}

    # Valeurs par défaut sûres
    surface  = float(surface_area) if surface_area and float(surface_area) > 0 else 100.0
    beds     = int(bedrooms)  if bedrooms  else 2
    baths    = int(bathrooms) if bathrooms else 1
    gar      = int(garage)    if garage    else 0

    # Features dérivées
    rooms_total      = beds + baths + gar
    surface_per_room = surface / max(rooms_total, 1)
    bath_bed_ratio   = baths   / max(beds, 1)
    log_surface      = math.log1p(surface)
    log_dist_mer     = math.log1p(dists["dist_mer"])
    log_dist_centre  = math.log1p(dists["dist_centre"])

    # Zone premium score (0-10 selon distance mer)
    zone_premium = max(0, 10 - dists["dist_mer"] * 2)

    # NLP
    nlp = _nlp_features(description, title)
    n_premium_feats = sum([
        nlp["has_standing"], nlp["has_piscine"], nlp["has_vue_mer"],
        nlp["has_gardiennage"], nlp["has_climatise"],
    ])

    # Prix m² médian par ville (valeur approx si non fourni)
    if city_prix_m2_median is None:
        city_m2 = {
            "almadies":1_800_000,"ngor":1_500_000,"mermoz":1_200_000,
            "ouakam":900_000,"plateau":1_100_000,"fann":1_000_000,
            "yoff":850_000,"pikine":400_000,"dakar":750_000,
            "guediawaye":350_000,"rufisque":300_000,"thies":250_000,
        }
        city_prix_m2_median = next(
            (v for k, v in city_m2.items() if k in city_key), 600_000
        )

    # Missing flags
    was_missing_surface  = int(not surface_area or float(surface_area) <= 0)
    was_missing_bedrooms = int(not bedrooms  or int(bedrooms)  <= 0)
    was_missing_bathrooms= int(not bathrooms or int(bathrooms) <= 0)

    row = {
        # Numériques bruts
        "surface_area":       surface,
        "bedrooms":           beds,
        "bathrooms":          baths,
        "garage":             gar,
        # Distances POI
        "dist_mer":           dists["dist_mer"],
        "dist_centre":        dists["dist_centre"],
        "dist_aeroport":      dists["dist_aeroport"],
        "dist_parc":          dists["dist_parc"],
        "dist_ucad":          dists["dist_ucad"],
        "dist_vdn":           dists["dist_vdn"],
        "dist_port":          dists["dist_port"],
        "dist_corniche":      dists["dist_corniche"],
        # Zone
        "zone_premium":       zone_premium,
        "is_premium":         is_premium,
        # Features dérivées
        "rooms_total":        rooms_total,
        "surface_per_room":   surface_per_room,
        "bath_bed_ratio":     bath_bed_ratio,
        "log_surface":        log_surface,
        "log_dist_mer":       log_dist_mer,
        "log_dist_centre":    log_dist_centre,
        # NLP (20 features)
        **nlp,
        "n_premium_feats":    n_premium_feats,
        # Missing flags
        "was_missing_surface_area": was_missing_surface,
        "was_missing_bedrooms":     was_missing_bedrooms,
        "was_missing_bathrooms":    was_missing_bathrooms,
        # Target encoding
        "city_prix_m2_median": city_prix_m2_median,
        # Catégorielles
        "property_type": property_type or "Appartement",
        "source":        source or "coinafrique",
    }

    return pd.DataFrame([row])


def predict_price(city=None, property_type=None, surface_area=None,
                  bedrooms=0, bathrooms=0, garage=0,
                  source="coinafrique",
                  description="", title="", **kwargs) -> dict:
    """
    Prédit le prix d'un bien immobilier.

    Paramètres
    ----------
    city          : str   — Ville/quartier (ex: "Almadies")
    property_type : str   — Type de bien (ex: "Villa")
    surface_area  : float — Superficie en m²
    bedrooms      : int   — Chambres
    bathrooms     : int   — Salles de bain
    garage        : int   — Garages (défaut 0)
    source        : str   — Source scrapy (défaut "coinafrique")
    description   : str   — Description de l'annonce (pour NLP)
    title         : str   — Titre de l'annonce (pour NLP)

    Retourne
    --------
    dict : predicted_price, price_min, price_max, model_used,
           confidence, r2, mae, mape
    """
    bundle   = _load()
    pipeline = bundle["pipeline"]
    metrics  = bundle.get("metrics", {})
    name     = bundle.get("best_model_name", "Modèle ML")

    # Construire les features
    X = _build_features(
        city=city, property_type=property_type,
        surface_area=surface_area, bedrooms=bedrooms,
        bathrooms=bathrooms, garage=garage,
        source=source, description=description, title=title,
    )

    # S'assurer que les colonnes sont dans le bon ordre
    expected = bundle.get("features", [])
    if expected:
        # Ajouter les colonnes manquantes avec 0
        for col in expected:
            if col not in X.columns:
                X[col] = 0
        X = X[expected]

    # Prédiction
    raw = pipeline.predict(X)[0]

    # Le modèle prédit log(price) ? Détecter automatiquement
    if raw < 30:   # log(5 milliards) ≈ 22 → c'est un log
        predicted = float(np.expm1(raw))
    else:
        predicted = float(raw)

    # Intervalle de confiance basé sur le MAPE du modèle
    mape = metrics.get("mape", 20.0)
    margin = predicted * (mape / 100)

    return {
        "predicted_price": round(max(predicted, 1_000_000)),
        "price_min":       round(max(predicted - margin, 500_000)),
        "price_max":       round(predicted + margin),
        "model_used":      name,
        "confidence":      f"±{mape:.0f}% (MAPE modèle)",
        "r2":              metrics.get("r2"),
        "mae":             metrics.get("mae"),
        "mape":            mape,
        "pct_20":          metrics.get("pct_20"),
    }
