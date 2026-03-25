"""
ImmoPredict SN — predict.py
Interface Django ↔ modèle ML (properties/ml/predict.py)
Reconstitue les 46 features depuis les 5 inputs du formulaire.
"""
import os
import math
import json
import joblib
import numpy as np
import pandas as pd

# ── Chemins ───────────────────────────────────────────────────────────────────
_DIR     = os.path.dirname(os.path.abspath(__file__))
_MODEL   = os.path.join(_DIR, 'model.pkl')
_CFG     = os.path.join(_DIR, 'features_config.json')

# ── GPS par quartier ──────────────────────────────────────────────────────────
CITY_GPS = {
    'almadies':            (14.745, -17.510),
    'ngor':                (14.749, -17.514),
    'yoff':                (14.758, -17.490),
    'ouakam':              (14.724, -17.494),
    'mermoz':              (14.710, -17.475),
    'plateau':             (14.693, -17.447),
    'fann':                (14.696, -17.460),
    'sacre-coeur':         (14.720, -17.461),
    'sacre coeur':         (14.720, -17.461),
    'vdn':                 (14.730, -17.470),
    'point e':             (14.694, -17.460),
    'sicap':               (14.712, -17.462),
    'liberte':             (14.715, -17.463),
    'hlm':                 (14.713, -17.459),
    'medina':              (14.695, -17.456),
    'grand yoff':          (14.736, -17.467),
    'dieuppeul':           (14.714, -17.457),
    'patte d\'oie':        (14.725, -17.460),
    'nord foire':          (14.742, -17.465),
    'parcelles':           (14.748, -17.451),
    'parcelles assainies': (14.748, -17.451),
    'pikine':              (14.755, -17.395),
    'guediawaye':          (14.778, -17.393),
    'thiaroye':            (14.755, -17.370),
    'yeumbeul':            (14.765, -17.348),
    'keur massar':         (14.765, -17.340),
    'mbao':                (14.740, -17.320),
    'rufisque':            (14.716, -17.274),
    'bargny':              (14.696, -17.239),
    'dakar':               (14.693, -17.447),
    'thies':               (14.791, -16.926),
    'mbour':               (14.368, -16.965),
    'saly':                (14.454, -17.012),
    'diamniadio':          (14.727, -17.184),
    'default':             (14.693, -17.447),
}

# ── Points d'intérêt ──────────────────────────────────────────────────────────
POI = {
    'dist_mer':      (14.693, -17.459),
    'dist_centre':   (14.693, -17.447),
    'dist_aeroport': (14.741, -17.490),
    'dist_aibd':     (14.738, -17.091),
    'dist_port':     (14.672, -17.427),
    'dist_ucad':     (14.692, -17.464),
    'dist_vdn':      (14.730, -17.470),
    'dist_corniche': (14.710, -17.470),
    'dist_parc':     (14.700, -17.458),
}

PREMIUM_ZONES = {
    'almadies', 'ngor', 'mermoz', 'fann', 'plateau',
    'sacre-coeur', 'sacre coeur', 'point e', 'vdn', 'yoff'
}

TYPE_MAP = {
    'villa':       ['villa'],
    'appartement': ['appart', 'f2', 'f3', 'f4', 'f5'],
    'terrain':     ['terrain', 'parcelle'],
    'duplex':      ['duplex'],
    'studio':      ['studio', 'f1'],
    'maison':      ['maison'],
    'local':       ['local', 'bureau', 'commerce'],
    'chambre':     ['chambre'],
}

NLP_FEATURES = [
    'has_standing', 'has_neuf', 'has_renove', 'has_piscine', 'has_meuble',
    'has_climatise', 'has_ascenseur', 'has_cuisine_amer', 'has_parking',
    'has_jardin', 'has_balcon', 'has_gardiennage', 'has_groupe_elec',
    'has_vue_mer', 'has_concierge', 'has_digicode', 'has_titre_foncier',
    'has_viabilise', 'has_invest', 'has_vue_ville',
]


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _get_gps(city):
    if not city: return CITY_GPS['default']
    k = city.lower().strip()
    if k in CITY_GPS: return CITY_GPS[k]
    for key, coords in CITY_GPS.items():
        if key in k or k in key: return coords
    return CITY_GPS['default']


def _normalize_type(ptype):
    if not ptype: return 'appartement'
    tl = ptype.lower()
    for key, kws in TYPE_MAP.items():
        if any(w in tl for w in [key] + kws): return key
    return 'appartement'


def _build_features(city, property_type, surface_area, bedrooms, bathrooms,
                    description='', city_stats=None, global_median=None):
    """Reconstitue toutes les features depuis les inputs utilisateur."""
    lat, lon = _get_gps(city)
    type_key = _normalize_type(property_type)
    city_key = (city or 'dakar').lower().strip()

    # Surface et chambres avec valeurs par défaut
    surface  = float(surface_area) if surface_area and float(surface_area) > 0 else 120.0
    beds     = float(bedrooms)     if bedrooms     and float(bedrooms) > 0     else 2.0
    baths    = float(bathrooms)    if bathrooms    and float(bathrooms) > 0    else 1.0

    # Distances POI
    dists = {col: _haversine(lat, lon, lat2, lon2) for col, (lat2, lon2) in POI.items()}

    # Zones
    is_premium   = int(any(z in city_key for z in PREMIUM_ZONES))
    zone_premium = max(0, 10 - dists['dist_mer'])

    # Features numériques dérivées
    rooms_total      = beds + baths
    surface_per_room = surface / max(rooms_total, 1)
    bath_bed_ratio   = baths / max(beds, 1)
    log_surface      = math.log1p(surface)

    # Target encoding ville
    if city_stats and city in city_stats:
        city_prix_m2_median = float(city_stats[city])
    elif global_median:
        city_prix_m2_median = float(global_median)
    else:
        # Fallback : prix médian par zone
        ZONE_BASE = {
            'almadies': 150_000_000, 'ngor': 120_000_000, 'mermoz': 90_000_000,
            'ouakam': 70_000_000,    'plateau': 80_000_000, 'fann': 85_000_000,
            'sicap': 55_000_000,     'pikine': 25_000_000,  'guediawaye': 22_000_000,
            'rufisque': 18_000_000,  'thies': 15_000_000,   'mbour': 20_000_000,
            'dakar': 60_000_000,
        }
        city_prix_m2_median = next(
            (v for k, v in ZONE_BASE.items() if k in city_key), 45_000_000
        )

    # NLP (description vide par défaut = 0)
    desc_lower = (description or '').lower()
    nlp = {feat: 0 for feat in NLP_FEATURES}

    row = {
        # Surfaces & pièces
        'surface_fill':           surface,
        'bedrooms_fill':          beds,
        'bathrooms_fill':         baths,
        'rooms_total':            rooms_total,
        'surface_per_room':       surface_per_room,
        'bath_bed_ratio':         bath_bed_ratio,
        'log_surface':            log_surface,
        # Distances
        **dists,
        'log_dist_mer':           math.log1p(dists['dist_mer']),
        'log_dist_centre':        math.log1p(dists['dist_centre']),
        # Géographie
        'zone_premium':           round(zone_premium, 2),
        'is_premium':             is_premium,
        # Missing flags (0 = valeur fournie)
        'was_missing_surface':    0 if surface_area else 1,
        'was_missing_bedrooms':   0 if bedrooms    else 1,
        'was_missing_bath':       0 if bathrooms   else 1,
        # Target encoding
        'city_prix_m2_median':    city_prix_m2_median,
        # Prestige composite
        'n_premium_feats':        is_premium,
        # NLP
        **nlp,
    }
    return row


def predict_price(city, property_type, surface_area=None,
                  bedrooms=None, bathrooms=None, description=''):
    """
    Prédit le prix d'un bien immobilier.

    Args:
        city           : Ville/quartier (str)
        property_type  : Type de bien (str)
        surface_area   : Surface en m² (float, optionnel)
        bedrooms       : Nombre de chambres (int, optionnel)
        bathrooms      : Nombre de SDB (int, optionnel)
        description    : Description du bien (str, optionnel)

    Returns:
        dict avec predicted_price, price_min, price_max, model_used, confidence
    """
    if not os.path.exists(_MODEL):
        raise FileNotFoundError(
            f"model.pkl introuvable dans {_DIR}. "
            "Exécutez NB3_Modelisation.ipynb puis NB4_Optimisation.ipynb."
        )

    # Charger le modèle
    data = joblib.load(_MODEL)
    pipeline  = data['pipeline']
    num_feats = data.get('numeric_features', [])
    cat_feats = data.get('categorical_features', [])
    metrics   = data.get('metrics', {})
    model_name = data.get('best_model_name', 'ML')

    # Charger target encoding si disponible
    city_stats   = None
    global_median = None
    try:
        encoders = joblib.load(os.path.join(_DIR, '..', '..', 'data', 'encoders.pkl'))
        cs = encoders.get('city_stats')
        if cs is not None:
            city_stats   = cs['city_price_target'].to_dict()
            global_median = cs['median'].mean()
    except: pass

    # Construire les features
    feats = _build_features(
        city, property_type, surface_area, bedrooms, bathrooms,
        description, city_stats, global_median
    )

    # Ajouter features catégorielles
    feats['property_type_clean'] = _normalize_type(property_type).capitalize()
    feats['source']              = 'coinafrique'  # valeur par défaut

    # Créer le DataFrame dans l'ordre attendu
    all_feats = num_feats + cat_feats
    X = pd.DataFrame([{f: feats.get(f, 0) for f in all_feats}])

    # Prédire
    log_pred = pipeline.predict(X)[0]

    # Reconvertir depuis log scale
    # Détecter si le modèle prédit en log ou en valeur brute
    if log_pred < 30:
        price = float(np.expm1(log_pred))
    else:
        price = float(log_pred)

    # Intervalle de confiance
    confidence_pct = metrics.get('mape', 20.0)
    margin = price * (confidence_pct / 100)
    price_min = max(price - margin, 100_000)
    price_max = price + margin

    return {
        'predicted_price': round(price),
        'price_min':       round(price_min),
        'price_max':       round(price_max),
        'model_used':      f'{model_name} (R²={metrics.get("r2",0):.3f})',
        'confidence':      f'±{confidence_pct:.0f}%',
        'r2':              metrics.get('r2', 0),
        'mape':            metrics.get('mape', 0),
        'pct20':           metrics.get('pct20', 0),
    }
