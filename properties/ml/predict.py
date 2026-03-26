"""
ImmoPredict SN — predict.py
Télécharge model.pkl depuis Google Drive si absent localement.
"""
import os, math, logging, joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_DIR   = os.path.dirname(os.path.abspath(__file__))
_MODEL = os.path.join(_DIR, 'model.pkl')

# ─── ID du fichier Google Drive ───────────────────────────────
GDRIVE_FILE_ID = "1T4UGRYKfDhEb-9pS-TMAI1Mwf6RDiMlk"
GDRIVE_FILE_ID = os.environ.get('GDRIVE_MODEL_ID', '')


def _download_model():
    """Télécharge model.pkl depuis Google Drive."""
    if not GDRIVE_FILE_ID:
        raise EnvironmentError(
            "Variable d'environnement GDRIVE_MODEL_ID non définie. "
            "Ajoutez-la dans Render > Environment."
        )

    try:
        import gdown
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install',
                               'gdown', '--quiet', '--break-system-packages'])
        import gdown

    url = f"https://drive.google.com/uc?id={GDRIVE_FILE_ID}"
    logger.info(f"Téléchargement model.pkl depuis Google Drive (id={GDRIVE_FILE_ID})...")
    print(f"Téléchargement model.pkl depuis Google Drive...")

    os.makedirs(_DIR, exist_ok=True)
    gdown.download(url, _MODEL, quiet=False, fuzzy=True)

    if not os.path.exists(_MODEL):
        raise FileNotFoundError("Échec du téléchargement depuis Google Drive.")

    size_mb = os.path.getsize(_MODEL) / 1e6
    logger.info(f"model.pkl téléchargé : {size_mb:.1f} MB")
    print(f"✅ model.pkl téléchargé : {size_mb:.1f} MB")


def _load_model():
    """Charge le modèle, le télécharge si nécessaire."""
    if not os.path.exists(_MODEL):
        logger.warning("model.pkl absent — téléchargement depuis Google Drive")
        _download_model()
    return joblib.load(_MODEL)


# ─── GPS par quartier ──────────────────────────────────────────
CITY_GPS = {
    'almadies':(14.745,-17.510),'ngor':(14.749,-17.514),'yoff':(14.758,-17.490),
    'ouakam':(14.724,-17.494),'mermoz':(14.710,-17.475),'fann':(14.696,-17.460),
    'plateau':(14.693,-17.447),'sacre coeur':(14.720,-17.461),
    'sacre-coeur':(14.720,-17.461),'vdn':(14.730,-17.470),
    'point e':(14.694,-17.460),'sicap':(14.712,-17.462),
    'liberte':(14.715,-17.463),'hlm':(14.713,-17.459),
    'medina':(14.695,-17.456),'grand yoff':(14.736,-17.467),
    'dieuppeul':(14.714,-17.457),'patte d oie':(14.725,-17.460),
    'nord foire':(14.742,-17.465),'parcelles':(14.748,-17.451),
    'pikine':(14.755,-17.395),'guediawaye':(14.778,-17.393),
    'thiaroye':(14.755,-17.370),'yeumbeul':(14.765,-17.348),
    'keur massar':(14.765,-17.340),'mbao':(14.740,-17.320),
    'rufisque':(14.716,-17.274),'dakar':(14.693,-17.447),
    'thies':(14.791,-16.926),'mbour':(14.368,-16.965),
    'saly':(14.454,-17.012),'diamniadio':(14.727,-17.184),
    'default':(14.693,-17.447),
}
POI = {
    'dist_mer':(14.693,-17.459),'dist_centre':(14.693,-17.447),
    'dist_aeroport':(14.741,-17.490),'dist_aibd':(14.738,-17.091),
    'dist_port':(14.672,-17.427),'dist_ucad':(14.692,-17.464),
    'dist_vdn':(14.730,-17.470),
}
PREMIUM = {'almadies','ngor','mermoz','fann','plateau','sacre coeur',
           'sacre-coeur','point e','vdn','yoff'}
PERIPH  = {'pikine','guediawaye','thiaroye','yeumbeul','keur massar',
           'mbao','rufisque'}
TYPE_MAP = {
    'Villa':       ['villa'],
    'Appartement': ['appartement','appart','f1','f2','f3','f4','f5'],
    'Terrain':     ['terrain','parcelle'],
    'Studio':      ['studio'],
    'Chambre':     ['chambre'],
    'Duplex':      ['duplex'],
    'Maison':      ['maison'],
    'Bureau':      ['bureau','local','commerce'],
}
NLP_DEFAULTS = {
    'has_standing':0,'has_neuf':0,'has_renove':0,'has_piscine':0,
    'has_meuble':0,'has_clim':0,'has_ascenseur':0,'has_parking':0,
    'has_jardin':0,'has_balcon':0,'has_gardien':0,'has_groupe':0,
    'has_vue_mer':0,'has_tf':0,'has_viabilise':0,'has_cuisine_am':0,
    'has_invest':0,
}


def _hav(la1, lo1, la2, lo2):
    R = 6371.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2-la1), math.radians(lo2-lo1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _gps(city):
    k = str(city or '').lower().strip()
    if k in CITY_GPS: return CITY_GPS[k]
    for key, c in sorted(CITY_GPS.items(), key=lambda x: len(x[0]), reverse=True):
        if key in k: return c
    return CITY_GPS['default']


def _norm_type(pt):
    t = str(pt or '').lower()
    for label, kws in TYPE_MAP.items():
        if any(k in t for k in kws): return label
    return 'Appartement'


def predict_price(city, property_type, surface_area=None, bedrooms=None,
                  bathrooms=None, transaction='vente', description=''):
    """
    Prédit le prix. Télécharge model.pkl depuis Google Drive si absent.
    """
    data       = _load_model()
    txn_key    = 'Vente' if 'vente' in str(transaction).lower() else 'Location'

    # Chargement modèle (séparé Vente/Location ou global)
    if isinstance(data, dict) and txn_key in data and 'model' in data.get(txn_key, {}):
        info       = data[txn_key]
        pipeline   = info['model']
        num_feats  = info.get('features_num', info.get('numeric_features', []))
        cat_feats  = info.get('features_cat', info.get('categorical_features', []))
        metrics    = info.get('metrics', {})
        model_name = info.get('name', info.get('best_model_name', 'ML'))
    else:
        pipeline   = data.get('pipeline', data)
        num_feats  = data.get('numeric_features', [])
        cat_feats  = data.get('categorical_features', [])
        metrics    = data.get('metrics', {})
        model_name = data.get('best_model_name', 'ML')

    lat, lon  = _gps(city)
    type_norm = _norm_type(property_type)
    city_k    = str(city or '').lower().strip()

    surf = float(surface_area) if surface_area and float(surface_area or 0) > 0 else 120.0
    beds = float(bedrooms)     if bedrooms     and float(bedrooms or 0)  > 0 else 2.0
    bths = float(bathrooms)    if bathrooms    and float(bathrooms or 0) > 0 else max(1.0, beds*0.5)

    dists = {col: _hav(lat, lon, la, lo) for col, (la, lo) in POI.items()}
    zone  = 2 if any(z in city_k for z in PREMIUM) else (0 if any(z in city_k for z in PERIPH) else 1)

    row = {
        # Surface & pièces
        'surface':       surf, 'log_surf': math.log1p(surf), 'surf_sq': surf**0.5,
        'bedrooms':      beds, 'bathrooms_f': bths,
        'rooms':         beds + bths, 'surf_room': surf / max(beds+bths, 1),
        'bath_bed':      bths / max(beds, 1), 'zone_surf': zone * surf,
        # GPS
        'lat': lat, 'lon': lon, 'zone': zone,
        'is_premium':   int(any(z in city_k for z in PREMIUM)),
        'is_periphery': int(any(z in city_k for z in PERIPH)),
        'zone_score':   max(0, 10 - dists['dist_mer']),
        'is_location':  int(txn_key == 'Location'),
        # Distances
        **dists,
        'log_dist_mer':    math.log1p(dists['dist_mer']),
        'log_dist_centre': math.log1p(dists['dist_centre']),
        # Encodages (valeur neutre)
        'city_enc': 0, 'type_enc': 0,
        # Flags
        'surf_imp': 0 if surface_area else 1,
        'bed_imp':  0 if bedrooms     else 1,
        'prestige': 0,
        # NLP par défaut
        **NLP_DEFAULTS,
        # Catégorielles
        'type_norm':   type_norm,
        'source':      'coinafrique',
        'transaction': txn_key,
    }

    all_feats = num_feats + cat_feats
    X = pd.DataFrame([{f: row.get(f, 0) for f in all_feats}])

    log_pred = float(pipeline.predict(X)[0])
    price    = float(np.expm1(log_pred))

    conf   = float(metrics.get('mape', 25.0))
    margin = price * conf / 100

    return {
        'predicted_price': round(price),
        'price_min':       round(max(price - margin, 1000)),
        'price_max':       round(price + margin),
        'transaction':     txn_key,
        'unit':            '/mois' if txn_key == 'Location' else '',
        'model_used':      f"{model_name} (R²={metrics.get('r2', 0):.3f})",
        'confidence':      f"±{conf:.0f}%",
        'r2':              metrics.get('r2', 0),
        'mape':            conf,
    }