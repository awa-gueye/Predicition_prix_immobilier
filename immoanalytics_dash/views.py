import re, json, logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# ── Rôles ─────────────────────────────────────────────────────────────────────
def get_user_role(user):
    if user.is_superuser: return 'admin'
    return 'viewer'

def get_user_redirect(user):
    return '/dashboard/' if user.is_superuser else '/viewer/'

def _ctx(request, extra=None):
    d = {'user': request.user, 'role': get_user_role(request.user)}
    if extra: d.update(extra)
    return d

# ── Auth ──────────────────────────────────────────────────────────────────────
def register_view(request):
    if request.user.is_authenticated:
        return redirect(get_user_redirect(request.user))
    error = None
    if request.method == 'POST':
        uname = request.POST.get('username','').strip()
        email = request.POST.get('email','').strip()
        fname = request.POST.get('first_name','').strip()
        lname = request.POST.get('last_name','').strip()
        pwd   = request.POST.get('password','')
        pwd2  = request.POST.get('confirm_password','')
        if not uname or not email or not pwd:
            error = "Veuillez remplir tous les champs obligatoires."
        elif pwd != pwd2:
            error = "Les mots de passe ne correspondent pas."
        elif len(pwd) < 8:
            error = "Le mot de passe doit contenir au moins 8 caractères."
        elif User.objects.filter(username=uname).exists():
            error = "Ce nom d'utilisateur est déjà pris."
        elif email and User.objects.filter(email=email).exists():
            error = "Cette adresse email est déjà utilisée."
        else:
            u = User.objects.create_user(username=uname, email=email, password=pwd,
                                          first_name=fname, last_name=lname)
            login(request, u)
            messages.success(request, f"Bienvenue {fname or uname} !")
            return redirect('/viewer/')
    return render(request, 'immoanalytics/register.html', {
        'error': error,
        'features': [
            'Recherche en langage naturel',
            'Prédiction ML des prix',
            'Carte interactive des annonces',
            '5 sources de données agrégées',
        ],
    })

def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_user_redirect(request.user))
    error = None
    if request.method == 'POST':
        uname    = request.POST.get('username','').strip()
        pwd      = request.POST.get('password','')
        remember = bool(request.POST.get('remember'))
        user     = authenticate(request, username=uname, password=pwd)
        if user and user.is_active:
            login(request, user)
            if not remember: request.session.set_expiry(0)
            return redirect(request.GET.get('next') or get_user_redirect(user))
        error = "Identifiants incorrects ou compte désactivé."
    return render(request, 'immoanalytics/login.html', {'error': error})

def logout_view(request):
    logout(request)
    return redirect('/immo/login/')

@login_required(login_url='/immo/login/')
def profile_view(request):
    u = request.user
    perms = [
        ('fa-chart-line',     'Dashboard',       u.is_staff or u.is_superuser),
        ('fa-chart-bar',      'Analytics',       u.is_staff or u.is_superuser),
        ('fa-map-marked-alt', 'Carte',           u.is_staff or u.is_superuser),
        ('fa-robot',          'Recherche IA',    True),
        ('fa-calculator',     'Estimation prix', True),
        ('fa-crown',          'Admin Panel',     u.is_superuser),
    ]
    return render(request, 'immoanalytics/profile.html', _ctx(request, {'perms': perms}))

@login_required(login_url='/immo/login/')
def settings_view(request):
    u = request.user
    if request.method == 'POST':
        a = request.POST.get('action')
        if a == 'update_profile':
            u.first_name = request.POST.get('first_name','').strip()
            u.last_name  = request.POST.get('last_name','').strip()
            e = request.POST.get('email','').strip()
            if e: u.email = e
            u.save()
            messages.success(request, "Profil mis à jour.")
        elif a == 'change_password':
            cur = request.POST.get('current_password','')
            new = request.POST.get('new_password','')
            cfm = request.POST.get('confirm_password','')
            if not u.check_password(cur):
                messages.error(request, "Mot de passe actuel incorrect.")
            elif new != cfm:
                messages.error(request, "Les mots de passe ne correspondent pas.")
            elif len(new) < 8:
                messages.error(request, "Minimum 8 caractères.")
            else:
                u.set_password(new); u.save()
                update_session_auth_hash(request, u)
                messages.success(request, "Mot de passe modifié.")
        return redirect('/immo/settings/')
    return render(request, 'immoanalytics/settings.html', _ctx(request))

# ── Dashboards Dash (iframe) ──────────────────────────────────────────────────
@login_required(login_url='/immo/login/')
def dashboard_page(request):
    return render(request, 'immoanalytics/dash_page.html', _ctx(request, {
        'page_title': 'Dashboard', 'dash_app_id': 'MainDashboard',
    }))

@login_required(login_url='/immo/login/')
def analytics_page(request):
    return render(request, 'immoanalytics/dash_page.html', _ctx(request, {
        'page_title': 'Analytics', 'dash_app_id': 'AnalyticsDashboard',
    }))

@login_required(login_url='/immo/login/')
def admin_panel_page(request):
    if not request.user.is_superuser:
        return redirect('/immo/login/')
    return render(request, 'immoanalytics/dash_page.html',
                  _ctx(request, {'page_title':'Admin Panel','dash_app_id':'AdminPanel'}))

# ── Carte géographique (Django pure, Leaflet.js) ──────────────────────────────
@login_required(login_url='/immo/login/')
def map_page(request):
    props = _load_geo()
    return render(request, 'immoanalytics/map.html', _ctx(request, {
        'props_json': json.dumps(props), 'total': len(props),
    }))

def _load_geo():
    try:
        from properties.models import CoinAfriqueProperty, DakarVenteProperty, ImmoSenegalProperty
        props = []
        for model, src in [(CoinAfriqueProperty,'coinafrique'),
                            (DakarVenteProperty,'dakarvente'),
                            (ImmoSenegalProperty,'immosenegal')]:
            for p in model.objects.filter(
                latitude__isnull=False, longitude__isnull=False, price__gt=0
            ).values('title','price','city','property_type','latitude','longitude')[:600]:
                lat, lon = float(p['latitude'] or 0), float(p['longitude'] or 0)
                if 12 < lat < 17 and -18 < lon < -14:
                    props.append({'t': str(p.get('title','') or '')[:50],
                                  'p': int(p['price'] or 0),
                                  'c': str(p.get('city','') or ''),
                                  'k': str(p.get('property_type','') or ''),
                                  'lat': round(lat,5), 'lon': round(lon,5), 's': src})
        return props
    except Exception as e:
        logger.warning(f"Carte: {e}")
        return _demo_geo()

def _demo_geo():
    import random; random.seed(42)
    cities = [('Almadies',14.745,-17.510),('Ngor',14.749,-17.514),
              ('Ouakam',14.724,-17.494),('Mermoz',14.710,-17.475),
              ('Plateau',14.693,-17.447),('Pikine',14.755,-17.395),
              ('Yoff',14.758,-17.490),('Fann',14.696,-17.460)]
    types = ['Villa','Appartement','Terrain','Duplex']
    return [{'t':f"{random.choice(types)} à {c[0]}",'p':random.randint(15,400)*1_000_000,
             'c':c[0],'k':random.choice(types),
             'lat':round(c[1]+random.uniform(-.02,.02),5),
             'lon':round(c[2]+random.uniform(-.02,.02),5),'s':'demo'}
            for c in cities*25]

# ── Estimation de prix ────────────────────────────────────────────────────────
@login_required(login_url='/immo/login/')
def estimation_page(request):
    cities = _get_cities()
    types  = [
        'Villa','Appartement','Terrain','Duplex','Studio',
        'Maison','Chambre','Local commercial','Bureau',
    ]
    transactions = [
        ('vente',    'Achat / Vente'),
        ('location', 'Location mensuelle'),
    ]
    result = error = None; form = {}
    if request.method == 'POST':
        form = {k: request.POST.get(k,'') for k in
                ['city','property_type','surface_area','bedrooms','bathrooms','transaction']}
        try:
            sa  = float(form['surface_area']) if form['surface_area'] else None
            bd  = int(form['bedrooms'])        if form['bedrooms']     else 0
            bh  = int(form['bathrooms'])       if form['bathrooms']    else 0
            txn = form.get('transaction','vente') or 'vente'
            result = _estimate(form['city'], form['property_type'], sa, bd, bh,
                                transaction=txn)
        except Exception as e:
            error = str(e)
    return render(request, 'immoanalytics/estimation.html',
                  _ctx(request, {
                      'cities': cities, 'types': types,
                      'transactions': transactions,
                      'result': result, 'error': error, 'form': form,
                  }))

# ── Prix de référence par type et transaction (FCFA) ─────────────────────────
# Sources : moyennes observées sur le marché sénégalais
# Format : (prix_min, prix_typique, prix_max)
PRIX_REF = {
    # Location mensuelle
    ("chambre",      "location"): (30_000,      70_000,       150_000),
    ("studio",       "location"): (60_000,      120_000,      300_000),
    ("f1",           "location"): (60_000,      120_000,      300_000),
    ("appartement",  "location"): (150_000,     400_000,    1_500_000),
    ("villa",        "location"): (300_000,   1_200_000,    5_000_000),
    ("duplex",       "location"): (250_000,     800_000,    3_000_000),
    ("maison",       "location"): (80_000,      250_000,      800_000),
    ("bureau",       "location"): (200_000,     600_000,    3_000_000),
    ("local",        "location"): (150_000,     400_000,    2_000_000),
    # Vente
    ("chambre",      "vente"):    (500_000,   2_000_000,    8_000_000),
    ("studio",       "vente"):    (2_000_000, 8_000_000,   25_000_000),
    ("appartement",  "vente"):    (8_000_000,40_000_000,  200_000_000),
    ("villa",        "vente"):    (20_000_000,100_000_000,500_000_000),
    ("duplex",       "vente"):    (15_000_000,70_000_000, 300_000_000),
    ("terrain",      "vente"):    (2_000_000, 20_000_000, 300_000_000),
    ("maison",       "vente"):    (5_000_000, 30_000_000, 150_000_000),
    ("local",        "vente"):    (10_000_000,50_000_000, 300_000_000),
}

# Multiplicateurs par zone géographique
ZONE_MULT = {
    "almadies":3.5,"ngor":3.0,"mermoz":2.5,"ouakam":2.0,"fann":2.2,
    "plateau":2.0,"yoff":1.8,"sacre coeur":2.3,"vdn":1.9,"point e":2.1,
    "sicap":1.5,"liberte":1.5,"hlm":1.3,"pikine":0.7,"guediawaye":0.65,
    "rufisque":0.55,"thies":0.5,"mbour":0.6,"saly":1.2,"dakar":1.0,
}


def _detect_transaction(ptype_raw):
    """Détecte si c'est vente ou location selon le type saisi."""
    tl = (ptype_raw or "").lower()
    loc_kw = ["louer","location","locat","bail","mois","mensuel","loyer"]
    if any(k in tl for k in loc_kw):
        return "location"
    return "vente"


def _normalize_type(ptype):
    """Normalise le type de bien vers une clé PRIX_REF."""
    if not ptype: return "appartement"
    tl = ptype.lower()
    if any(w in tl for w in ["chambre","room"]): return "chambre"
    if any(w in tl for w in ["studio","f1","t1"]): return "studio"
    if any(w in tl for w in ["villa","maison individuelle"]): return "villa"
    if any(w in tl for w in ["appart","f2","f3","f4","f5","t2","t3"]): return "appartement"
    if any(w in tl for w in ["terrain","parcelle","lot"]): return "terrain"
    if any(w in tl for w in ["duplex","triplex"]): return "duplex"
    if any(w in tl for w in ["maison","bungalow"]): return "maison"
    if any(w in tl for w in ["bureau","office","local","commerce"]): return "local"
    return tl.split()[0] if tl else "appartement"


def _estimate(city, ptype, surface, bedrooms, bathrooms, transaction=None):
    """
    Estimation du prix d'un bien immobilier.
    1. Essaie le modèle ML si disponible.
    2. Sinon, utilise les prix de référence réels par type + zone.
    """
    import os, sys, importlib

    # ── 1. Modèle ML (si disponible) ─────────────────────────────────────────
    ml_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'properties', 'ml'))
    if os.path.exists(os.path.join(ml_dir, 'predict.py')):
        if ml_dir not in sys.path:
            sys.path.insert(0, ml_dir)
        try:
            mod = importlib.import_module('predict')
            return mod.predict_price(
                city=city, property_type=ptype,
                surface_area=surface, bedrooms=bedrooms, bathrooms=bathrooms)
        except Exception as e:
            logger.warning(f"ML: {e}")

    # ── 2. Estimation statistique depuis la DB ────────────────────────────────
    type_key = _normalize_type(ptype)
    txn      = transaction or _detect_transaction(ptype)

    # Chercher dans la DB des biens similaires
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
                                        LogerDakarProperty, DakarVenteProperty,
                                        ImmoSenegalProperty)
        from django.db.models import Avg, Count
        import statistics as stats

        KW_LOC = ["louer","location","locat","bail","mensuel","loyer"]
        KW_VTE = ["vendre","vente","achat","cession"]

        MODELS = [CoinAfriqueProperty, ExpatDakarProperty,
                  LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty]
        prices = []
        for model in MODELS:
            qs = model.objects.filter(price__gt=0, price__lt=5_000_000_000)
            if city:  qs = qs.filter(city__icontains=city[:6])
            if ptype: qs = qs.filter(property_type__icontains=type_key[:5])
            # Filtre transaction via titre/statut
            from django.db.models import Q
            avail = [f.name for f in model._meta.get_fields()]
            if txn == "location":
                q = Q()
                for k in KW_LOC:
                    q |= Q(title__icontains=k)
                    if "statut" in avail: q |= Q(statut__icontains=k)
                qs = qs.filter(q)
            elif txn == "vente":
                q = Q()
                for k in KW_VTE:
                    q |= Q(title__icontains=k)
                    if "statut" in avail: q |= Q(statut__icontains=k)
                qs = qs.filter(q)
            batch = list(qs.values_list("price", flat=True)[:200])
            prices.extend(batch)

        if len(prices) >= 5:
            # Utiliser la médiane (plus robuste que la moyenne pour l'immobilier)
            base = stats.median(prices)
        else:
            base = None
    except Exception as e:
        logger.warning(f"DB estimate: {e}")
        base = None

    # ── 3. Fallback : prix de référence par type + zone ───────────────────────
    if not base:
        ref_key = (type_key, txn)
        # Chercher la clé exacte ou la plus proche
        ref = PRIX_REF.get(ref_key)
        if not ref:
            # Chercher uniquement par type
            for k, v in PRIX_REF.items():
                if k[0] == type_key:
                    ref = v; break
        if not ref:
            ref = PRIX_REF.get(("appartement", txn),
                                (1_000_000, 30_000_000, 100_000_000))
        base = ref[1]  # Prix typique

    # ── 4. Ajustements ────────────────────────────────────────────────────────
    # Multiplicateur de zone
    city_key = (city or "dakar").lower().strip()
    zone_mult = 1.0
    for zone, mult in ZONE_MULT.items():
        if zone in city_key:
            zone_mult = mult
            break

    base *= zone_mult

    # Surface (seulement pour les biens dont le prix dépend de la surface)
    if surface and surface > 0 and type_key not in ("chambre","terrain"):
        # Prix au m² de référence selon le type
        prix_m2_ref = {
            "appartement": 400_000 if txn=="vente" else 2_500,
            "villa":        600_000 if txn=="vente" else 4_000,
            "duplex":       500_000 if txn=="vente" else 3_000,
            "maison":       300_000 if txn=="vente" else 1_500,
            "studio":       450_000 if txn=="vente" else 2_000,
            "local":        500_000 if txn=="vente" else 3_500,
            "bureau":       600_000 if txn=="vente" else 5_000,
        }
        pm2 = prix_m2_ref.get(type_key, 350_000 if txn=="vente" else 2_000)
        surface_price = surface * pm2 * zone_mult
        # Pondérer : 60% surface, 40% base statistique
        base = base * 0.4 + surface_price * 0.6

    # Chambres (ajustement mineur)
    if bedrooms and bedrooms > 1 and type_key not in ("chambre","studio","terrain"):
        base *= (1 + (bedrooms - 1) * 0.05)

    base = max(base, 10_000)   # Minimum absolu 10 000 FCFA
    margin = base * 0.20

    # Label de l'unité selon le type de transaction
    unit = "/mois" if txn == "location" else ""
    label = f"Estimation {type_key}"
    if txn == "location": label += " (location mensuelle)"

    return {
        "predicted_price": round(base),
        "price_min":       round(max(base - margin, 10_000)),
        "price_max":       round(base + margin),
        "model_used":      label,
        "confidence":      "±20%",
        "transaction":     txn,
        "unit":            unit,
    }

def _zone_base(city):
    zones = {'almadies':240_000_000,'ngor':180_000_000,'ouakam':110_000_000,
             'mermoz':100_000_000,'plateau':80_000_000,'yoff':85_000_000,
             'pikine':28_000_000,'dakar':65_000_000,'thies':20_000_000}
    cl = (city or '').lower()
    return next((v for k,v in zones.items() if k in cl), 55_000_000)

def _get_cities():
    try:
        from properties.models import CoinAfriqueProperty
        cs = CoinAfriqueProperty.objects.values_list("city",flat=True).distinct().order_by("city")[:60]
        return sorted(set(c.strip() for c in cs if c and c.strip()))
    except:
        return ["Almadies","Dakar","Fann","Guediawaye","Mermoz","Ngor",
                "Ouakam","Pikine","Plateau","Rufisque","Thies","Yoff"]


# ── Réponses analytiques ──────────────────────────────────────────────────────


PRICE_MIN = 1_000_000
PRICE_MAX = 5_000_000_000

KW_LOC = ["louer","location","locat","bail","mensuel","loyer","a louer","par mois"]
KW_VTE = ["vendre","acheter","achat","vente","a vendre"]


def _get_db_data():
    """Charge toutes les données valides depuis la DB (prix >= 10 000 FCFA)."""
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty)
        MODELS = [CoinAfriqueProperty, ExpatDakarProperty,
                  LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty]
        results = []
        for model in MODELS:
            for p in model.objects.filter(
                price__gte=10_000, price__lte=PRICE_MAX
            ).values("price","city","property_type","surface_area",
                     "bedrooms","statut","title")[:3000]:
                results.append(p)
        return results
    except Exception as e:
        logger.warning(f"DB data: {e}")
        return []


def _search(crit):
    """Recherche dans toutes les tables avec filtres."""
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty)
        MODELS = [(CoinAfriqueProperty,"coinafrique"),(ExpatDakarProperty,"expat_dakar"),
                  (LogerDakarProperty,"loger_dakar"),(DakarVenteProperty,"dakarvente"),
                  (ImmoSenegalProperty,"immosenegal")]
        results = []
        for model, src in MODELS:
            qs = model.objects.filter(price__gte=10_000, price__lte=PRICE_MAX)
            if crit.get("city"):      qs = qs.filter(city__icontains=crit["city"])
            if crit.get("type"):      qs = qs.filter(property_type__icontains=crit["type"])
            if crit.get("min_price"): qs = qs.filter(price__gte=crit["min_price"])
            if crit.get("max_price"): qs = qs.filter(price__lte=crit["max_price"])
            if crit.get("bedrooms"):  qs = qs.filter(bedrooms__gte=crit["bedrooms"])
            for p in qs.order_by("price").values(
                "id","title","price","city","property_type",
                "surface_area","bedrooms","url")[:80]:
                results.append({**p, "source": src})
        seen, deduped = set(), []
        for r in sorted(results, key=lambda x: x.get("price") or 0):
            key = (r.get("price"), str(r.get("city",""))[:8], str(r.get("property_type",""))[:8])
            if key not in seen:
                seen.add(key); deduped.append(r)
        return deduped, len(deduped)
    except Exception as e:
        logger.warning(f"Search: {e}")
        return [], 0



def _is_greeting(text):
    tl = text.lower().strip().rstrip("!?.,")
    return tl in GREETINGS or len(tl.replace(" ","")) < 4


def _detect_intent(text):
    """Détecte l'intention analytique ou recherche."""
    import re
    tl = (text.lower()
          .replace("é","e").replace("è","e").replace("à","a")
          .replace("ê","e").replace("â","a").replace("ç","c")
          .replace("\u2019","'").replace("\u2018","'"))
    for pattern, intent in ANALYTIC_PATTERNS:
        if re.search(pattern, tl):
            return intent
    return "recherche"


def _fmt_price(price):
    if not price or float(price) < 100: return "—"
    p = float(price)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _amt(t, unit=""):
    """Convertit un texte en montant FCFA avec unité optionnelle."""
    try:
        v = float(str(t).replace(" ","").replace(",","."))
        if v <= 0: return None
        u = (unit or "").lower().strip()
        if u in ("m","million","millions"):     return v * 1_000_000
        if u in ("mds","milliard","milliards"): return v * 1_000_000_000
        if u in ("k","mille","millier"):        return v * 1_000
        # Sans unité : < 1000 → millions, sinon valeur brute
        if v < 1_000: return v * 1_000_000
        return v
    except:
        return None


def _parse(text):
    """Extrait les critères depuis le texte naturel."""
    import re
    tl = (text.lower()
          .replace("é","e").replace("è","e").replace("à","a")
          .replace("ê","e").replace("â","a").replace("ç","c")
          .replace("\u2019","'").replace("\u2018","'"))
    mn = mx = None
    NB  = r"([\d][\d\s]*(?:[.,][\d]+)?)"
    UNI = r"\s*(m\b|millions?|mds|milliard|k\b|mille|fcfa|cfa)?"

    m = re.search(r"entre\s+" + NB + UNI + r"\s*(?:et|-)\s*" + NB + UNI, tl)
    if m:
        mn = _amt(m.group(1).replace(" ",""), m.group(2) or "")
        mx = _amt(m.group(3).replace(" ",""), m.group(4) or "")
    else:
        m2 = re.search(r"(?:moins de|max|pas plus de|jusqu.a)\s+" + NB + UNI, tl)
        if m2: mx = _amt(m2.group(1).replace(" ",""), m2.group(2) or "")
        m3 = re.search(r"(?:a partir de|au moins|minimum|plus de)\s+" + NB + UNI, tl)
        if m3: mn = _amt(m3.group(1).replace(" ",""), m3.group(2) or "")
        if not m2 and not m3:
            m4 = re.search(NB + r"\s*(m\b|millions?|mds|milliard)", tl)
            if m4:
                v = _amt(m4.group(1).replace(" ",""), m4.group(2))
                if v: mn = v * 0.7; mx = v * 1.4
            if not mx and not mn:
                m5 = re.search(r"([\d]{4,})\s*(?:fcfa|cfa)?", tl)
                if m5:
                    v = _amt(m5.group(1))
                    if v: mn = v * 0.7; mx = v * 1.4

    if mn and mn <= 0: mn = None
    if mx and mx <= 0: mx = None

    city  = next((c.title() for c in sorted(CITIES_SN, key=len, reverse=True)
                  if c in tl), None)
    ptype = next((k.capitalize() for k, kws in TYPE_MAP.items()
                  if any(w in tl for w in [k]+kws)), None)
    txn   = ("location" if any(k in tl for k in KW_LOC)
             else "vente" if any(k in tl for k in KW_VTE)
             else None)
    beds = None
    mb = re.search(r"(\d+)\s*chambre", tl)
    if mb: beds = int(mb.group(1))
    mb2 = re.search(r"\bf(\d)\b", tl)
    if mb2: beds = max(1, int(mb2.group(1))-1)

    return {"city":city,"type":ptype,"transaction":txn,
            "min_price":mn,"max_price":mx,"bedrooms":beds}


def _analyze_prix_stats(question, crit):
    """Calcule les statistiques de prix pour répondre à 'Que vaut X à Y ?'."""
    import statistics
    data = _get_db_data()
    if not data:
        return "Je n'ai pas accès aux données en ce moment.", []

    # Filtrer
    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if crit.get("city"):
        city_q = crit["city"].lower()
        filtered = [d for d in filtered
                    if str(d.get("city","")).lower().find(city_q[:5]) >= 0]
    if crit.get("type"):
        type_q = crit["type"].lower()
        filtered = [d for d in filtered
                    if str(d.get("property_type","")).lower().find(type_q[:4]) >= 0]

    if not filtered:
        scope = []
        if crit.get("city"):  scope.append(f"à {crit['city']}")
        if crit.get("type"):  scope.append(crit["type"])
        return (f"Aucune donnée disponible pour {' '.join(scope) or 'cette recherche'}. "
                "Essayez un autre quartier ou type de bien."), []

    prices = [d["price"] for d in filtered]
    p_med  = statistics.median(prices)
    p_moy  = statistics.mean(prices)
    p_min  = min(prices)
    p_max  = max(prices)
    n      = len(prices)

    # Construire la réponse
    scope_parts = []
    if crit.get("type"):  scope_parts.append(f"<b>{crit['type']}</b>")
    if crit.get("city"):  scope_parts.append(f"à <b>{crit['city']}</b>")
    scope = " ".join(scope_parts) if scope_parts else "ce type de bien"

    lines = [
        f"Analyse sur <b>{n}</b> annonce{'s' if n>1 else ''} {scope} :",
        f"• Prix minimum : <b>{_fmt_price(p_min)}</b>",
        f"• Prix médian  : <b>{_fmt_price(p_med)}</b>",
        f"• Prix moyen   : <b>{_fmt_price(p_moy)}</b>",
        f"• Prix maximum : <b>{_fmt_price(p_max)}</b>",
    ]

    # Exemples de biens
    props = []
    for d in sorted(filtered, key=lambda x: abs(x["price"]-p_med))[:5]:
        props.append({
            "title":     str(d.get("title","") or "Annonce")[:55],
            "price":     d["price"],
            "price_fmt": _fmt_price(d["price"]),
            "city":      str(d.get("city","") or ""),
            "type":      str(d.get("property_type","") or ""),
            "source":    "",
            "surface":   d.get("surface_area",""),
            "bedrooms":  d.get("bedrooms",""),
        })
    return "<br>".join(lines), props


def _analyze_comparaison(question, crit):
    """Compare les prix entre quartiers ou types de biens."""
    import statistics
    data = _get_db_data()
    if not data:
        return "Données indisponibles.", []

    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if crit.get("type"):
        type_q = crit["type"].lower()
        filtered = [d for d in filtered
                    if str(d.get("property_type","")).lower().find(type_q[:4]) >= 0]

    # Grouper par ville
    from collections import defaultdict
    by_city = defaultdict(list)
    for d in filtered:
        city = str(d.get("city","") or "").strip().title()
        if city and city != "Inconnu":
            by_city[city].append(d["price"])

    # Top 8 villes avec le plus d'annonces
    top = sorted([(c, ps) for c, ps in by_city.items() if len(ps) >= 5],
                 key=lambda x: statistics.median(x[1]), reverse=True)[:8]

    if not top:
        return "Pas assez de données pour comparer les quartiers.", []

    scope = f"({crit['type']})" if crit.get("type") else ""
    lines = [f"Comparaison des prix médians par quartier {scope} :"]
    for city, prices in top:
        med = statistics.median(prices)
        lines.append(f"• <b>{city}</b> : {_fmt_price(med)} ({len(prices)} annonces)")

    cheaper = top[-1]
    pricier = top[0]
    lines.append(
        f"<br><b>{pricier[0]}</b> est le quartier le plus cher "
        f"et <b>{cheaper[0]}</b> le plus abordable."
    )
    return "<br>".join(lines), []


def _analyze_stats_marche(question, crit):
    """Donne une vue d'ensemble du marché."""
    import statistics
    data = _get_db_data()
    if not data:
        return "Données indisponibles.", []

    total  = len([d for d in data if d.get("price") and d["price"] >= PRICE_MIN])
    prices = [d["price"] for d in data if d.get("price") and d["price"] >= PRICE_MIN]

    if not prices:
        return "Données insuffisantes.", []

    # Compter par type
    from collections import Counter
    types = Counter(str(d.get("property_type","") or "").strip() for d in data
                    if d.get("price") and d["price"] >= PRICE_MIN)
    top_types = types.most_common(4)

    lines = [
        f"<b>Marché immobilier au Sénégal</b> — aperçu sur <b>{total:,}</b> annonces :",
        f"• Prix médian global : <b>{_fmt_price(statistics.median(prices))}</b>",
        f"• Prix moyen global  : <b>{_fmt_price(statistics.mean(prices))}</b>",
        f"• Prix minimum       : <b>{_fmt_price(min(prices))}</b>",
        f"• Prix maximum       : <b>{_fmt_price(max(prices))}</b>",
        "",
        "<b>Répartition par type :</b>",
    ]
    for t, n in top_types:
        lines.append(f"• {t or 'Autre'} : <b>{n:,}</b> annonces")

    return "<br>".join(lines), []


def _analyze_budget(question, crit):
    """Conseille sur ce qu'on peut trouver avec un budget donné."""
    import statistics
    mn = crit.get("min_price") or crit.get("max_price")
    mx = crit.get("max_price") or (mn * 1.4 if mn else None)
    if not mx:
        # Essayer d'extraire un montant brut depuis la question
        import re as _re
        m = _re.search(r"(\d[\d\s]{1,12}\d)\s*(?:fcfa|cfa|f)?", question.lower())
        if m:
            v = _amt(m.group(1).replace(" ",""))
            if v and v >= 500_000:
                mx = v
                mn = v * 0.7
    if not mx:
        return ("Précisez votre budget pour que je puisse vous conseiller.<br>"
                "<small style='opacity:.65'>Exemples :<br>"
                "• <em>Avec 200M FCFA que puis-je acheter ?</em><br>"
                "• <em>Avec un budget de 50 000 000 FCFA à Dakar</em><br>"
                "• <em>Budget 150M, quel bien à Ouakam ?</em></small>"), []

    data = _get_db_data()
    filtered = [d for d in data
                if d.get("price") and PRICE_MIN <= d["price"] <= mx * 1.1]
    if crit.get("city"):
        city_q = crit["city"].lower()
        filtered = [d for d in filtered
                    if str(d.get("city","")).lower().find(city_q[:5]) >= 0]

    if not filtered:
        return (f"Avec un budget de <b>{_fmt_price(mx)}</b>, "
                "il n'y a pas d'annonces correspondantes. "
                "Essayez un budget plus élevé ou un autre quartier."), []

    from collections import Counter
    types = Counter(str(d.get("property_type","") or "").strip()
                    for d in filtered if d.get("price") and d["price"] <= mx)
    budget_filtered = [d for d in filtered if d.get("price") and d["price"] <= mx]

    loc = f"à {crit['city']}" if crit.get("city") else "au Sénégal"
    lines = [
        f"Avec <b>{_fmt_price(mx)}</b> {loc}, vous pouvez trouver :",
    ]
    for t, n in types.most_common(5):
        if n > 0:
            prices = [d["price"] for d in budget_filtered
                      if str(d.get("property_type","")).strip() == t]
            if prices:
                lines.append(f"• <b>{n} {t}{'s' if n>1 else ''}</b> "
                              f"(de {_fmt_price(min(prices))} à {_fmt_price(max(prices))})")

    props = []
    for d in sorted(budget_filtered, key=lambda x: x.get("price",0), reverse=True)[:5]:
        props.append({
            "title":     str(d.get("title","") or "Annonce")[:55],
            "price":     d["price"],
            "price_fmt": _fmt_price(d["price"]),
            "city":      str(d.get("city","") or ""),
            "type":      str(d.get("property_type","") or ""),
            "source":    "",
            "surface":   d.get("surface_area",""),
            "bedrooms":  d.get("bedrooms",""),
        })
    return "<br>".join(lines), props


def _analyze_recommandation(question, crit):
    """Recommande des quartiers selon le profil."""
    import statistics, re as _re
    tl = question.lower()

    # Détecter louer vs acheter
    is_loc = any(k in tl for k in KW_LOC)
    is_vte = any(k in tl for k in KW_VTE)

    data = _get_db_data()
    if not data:
        return "Données indisponibles.", []

    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if is_loc:
        filtered = [d for d in filtered
                    if any(k in str(d.get("statut","") or d.get("title","") or "").lower()
                           for k in KW_LOC)]
    elif is_vte:
        filtered = [d for d in filtered
                    if any(k in str(d.get("statut","") or d.get("title","") or "").lower()
                           for k in KW_VTE)]

    # Grouper par ville + calculer score (médiane + nb annonces)
    from collections import defaultdict
    by_city = defaultdict(list)
    for d in filtered:
        city = str(d.get("city","") or "").strip().title()
        if city and city != "Inconnu":
            by_city[city].append(d["price"])

    if not by_city:
        return "Pas assez de données pour faire une recommandation.", []

    # Score : équilibre prix et volume
    scored = []
    all_medians = [statistics.median(ps) for ps in by_city.values() if len(ps) >= 3]
    global_med  = statistics.median(all_medians) if all_medians else 1
    for city, prices in by_city.items():
        if len(prices) < 3: continue
        med   = statistics.median(prices)
        score = len(prices) * 0.4 + (1/(med/global_med + 0.001)) * 0.6
        scored.append((city, med, len(prices), score))

    scored.sort(key=lambda x: x[3], reverse=True)
    top_abordable = scored[:5]

    action = "louer" if is_loc else ("acheter" if is_vte else "investir")
    lines = [f"<b>Meilleures zones pour {action}</b> (rapport qualité/prix) :"]
    for city, med, n, _ in top_abordable:
        lines.append(f"• <b>{city}</b> : médiane <b>{_fmt_price(med)}</b> — {n} annonces")

    if is_loc:
        lines.append("<br>Ces quartiers offrent le meilleur choix de biens en location.")
    elif is_vte:
        lines.append("<br>Ces quartiers ont le plus d'offres et les meilleurs prix à l'achat.")
    else:
        lines.append("<br>Ces quartiers présentent le meilleur potentiel d'investissement.")

    return "<br>".join(lines), []



@login_required(login_url='/immo/login/')
def viewer_page(request):
    """Page Recherche IA — rendue côté serveur."""
    q     = request.GET.get('q', '')
    city  = request.GET.get('city', '')
    ptype = request.GET.get('type', '')
    txn   = request.GET.get('txn', '')
    min_p = request.GET.get('min_price', '')
    max_p = request.GET.get('max_price', '')
    min_b = request.GET.get('beds', '')
    results = []; total = 0; ai_msg = ''

    if q or city or ptype or txn or min_p or max_p or min_b:
        crit = _parse(q) if q else {}
        if city:  crit['city']        = city
        if ptype: crit['type']        = ptype
        if txn:   crit['transaction'] = txn
        try:
            if min_p: crit['min_price'] = float(min_p) * 1_000_000
            if max_p: crit['max_price'] = float(max_p) * 1_000_000
            if min_b: crit['bedrooms']  = int(min_b)
        except: pass
        results, total = _search(crit)
        parts = []
        if crit.get('city'):        parts.append(crit['city'])
        if crit.get('type'):        parts.append(crit['type'])
        if crit.get('transaction'): parts.append(crit['transaction'])
        mn, mx = crit.get('min_price'), crit.get('max_price')
        if mn and mx: parts.append(f"{mn/1e6:.0f}M–{mx/1e6:.0f}M FCFA")
        ai_msg = (f"{total} résultat(s) — " + " · ".join(parts)) if parts else f"{total} résultat(s)"

    return render(request, 'immoanalytics/viewer.html', _ctx(request, {
        'q': q, 'results': results[:24], 'total': total, 'ai_msg': ai_msg,
        'cities': _get_cities(), 'city': city, 'ptype': ptype, 'txn': txn,
        'min_p': min_p, 'max_p': max_p, 'min_b': min_b,
        'prop_types':   ['Villa', 'Appartement', 'Terrain', 'Duplex', 'Studio', 'Maison'],
        'beds_choices': ['1', '2', '3', '4', '5'],
    }))


@login_required(login_url='/immo/login/')
def api_chatbot(request):
    """Endpoint AJAX chatbot IA — recherche + analytique."""
    if request.method != 'POST':
        return JsonResponse({'error':'POST requis'}, status=405)
    try:
        body = json.loads(request.body)
        q    = body.get('message','').strip()
        if not q:
            return JsonResponse({'error':'Message vide'}, status=400)

        # ── Salutation ───────────────────────────────────────────────────────
        if _is_greeting(q):
            return JsonResponse({
                'response': (
                    "Bonjour ! Je suis votre assistant immobilier intelligent.<br>"
                    "Je peux vous aider à :<br>"
                    "• Rechercher des biens disponibles<br>"
                    "• Analyser les prix d'un quartier ou type de bien<br>"
                    "• Comparer les quartiers<br>"
                    "• Estimer ce que vous pouvez acheter avec votre budget<br>"
                    "• Recommander les meilleures zones<br>"
                    "<small style='opacity:.65'>Exemple : <em>Que vaut une villa à Almadies ?</em> "
                    "ou <em>Avec 80M FCFA, que puis-je acheter à Dakar ?</em></small>"
                ),
                'total':0, 'properties':[]
            })

        # ── Détecter l'intention ─────────────────────────────────────────────
        intent = _detect_intent(q)
        crit   = _parse(q)

        # ── Répondre selon l'intention ───────────────────────────────────────
        if intent == "prix_stats":
            response, props = _analyze_prix_stats(q, crit)
            return JsonResponse({'response':response,'total':len(props),'properties':props})

        elif intent == "comparaison":
            response, props = _analyze_comparaison(q, crit)
            return JsonResponse({'response':response,'total':0,'properties':props})

        elif intent == "stats_marche":
            response, props = _analyze_stats_marche(q, crit)
            return JsonResponse({'response':response,'total':0,'properties':props})

        elif intent == "budget_conseil":
            response, props = _analyze_budget(q, crit)
            return JsonResponse({'response':response,'total':len(props),'properties':props})

        elif intent == "recommandation":
            response, props = _analyze_recommandation(q, crit)
            return JsonResponse({'response':response,'total':0,'properties':props})

        else:
            # ── Recherche classique ──────────────────────────────────────────
            has_crit = any(crit.get(k) for k in ['city','type','transaction','min_price','max_price','bedrooms'])

            if not has_crit:
                return JsonResponse({
                    'response': (
                        "Je n'ai pas bien compris. Essayez :<br>"
                        "• <em>Villa à vendre Almadies moins de 300M</em><br>"
                        "• <em>Que vaut un appartement à Ouakam ?</em><br>"
                        "• <em>Avec 50M que puis-je acheter à Dakar ?</em><br>"
                        "• <em>Quel quartier est le moins cher pour louer ?</em>"
                    ),
                    'total':0, 'properties':[]
                })

            results, total = _search(crit)
            parts = []
            if crit.get('city'):        parts.append(f"<b>{crit['city']}</b>")
            if crit.get('type'):        parts.append(f"<b>{crit['type']}</b>")
            if crit.get('transaction'): parts.append(f"en <b>{crit['transaction']}</b>")
            if crit.get('bedrooms'):    parts.append(f"<b>{crit['bedrooms']}+ chambres</b>")
            mn, mx = crit.get('min_price'), crit.get('max_price')
            if mn and mx:   parts.append(f"budget <b>{_fmt_price(mn)} – {_fmt_price(mx)}</b>")
            elif mn:        parts.append(f"à partir de <b>{_fmt_price(mn)}</b>")
            elif mx:        parts.append(f"max <b>{_fmt_price(mx)}</b>")

            lines = []
            if parts:
                lines.append(f"Recherche : {', '.join(parts)}.")

            if total == 0:
                lines.append("Aucun bien trouvé. Essayez un autre quartier ou élargissez votre budget.")
            elif total == 1:
                p = results[0]["price"]
                lines.append(f"1 bien trouvé au prix de <b>{_fmt_price(p)}</b>.")
            else:
                lines.append(f"<b>{total}</b> biens trouvés.")
                prices = sorted([r["price"] for r in results if r.get("price") and r["price"] >= PRICE_MIN])
                if len(prices) >= 2:
                    lines.append(f"Prix : de <b>{_fmt_price(prices[0])}</b> à <b>{_fmt_price(prices[-1])}</b>.")

            props = []
            for p in results[:6]:
                price = p.get("price",0) or 0
                if price < PRICE_MIN: continue
                props.append({
                    "title":    str(p.get("title","") or "Annonce immobilière")[:60],
                    "price":    price,
                    "price_fmt":_fmt_price(price),
                    "city":     str(p.get("city","") or ""),
                    "type":     str(p.get("property_type","") or ""),
                    "source":   p.get("source",""),
                    "surface":  p.get("surface_area",""),
                    "bedrooms": p.get("bedrooms",""),
                })

            return JsonResponse({'response':" ".join(lines),'total':total,'properties':props})

    except Exception as e:
        logger.error(f"Chatbot: {e}")
        return JsonResponse({'response':"Une erreur s'est produite. Réessayez.",'total':0,'properties':[]})


def api_current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated':False},status=401)
    u=request.user; fn=u.get_full_name() or u.username
    return JsonResponse({'authenticated':True,'username':u.username,'full_name':fn,
                         'role':get_user_role(u),'initials':''.join(p[0].upper() for p in fn.split()[:2])})

def api_check_auth(request):
    if request.user.is_authenticated:
        return JsonResponse({'authenticated':True,'role':get_user_role(request.user)})
    return JsonResponse({'authenticated':False},status=401)
CITIES_SN = [
    "almadies","ngor","ouakam","mermoz","pikine","guediawaye","plateau","fann",
    "yoff","rufisque","liberte","hlm","sicap","grand yoff","keur massar",
    "medina","thies","mbour","dakar","parcelles","sacre coeur","vdn","saly",
    "patte d oie","dieuppeul","fass","colobane","biscuiterie","nord foire",
    "mbao","yeumbeul","diamniadio","bargny","malika",
]
TYPE_MAP = {
    "villa":["villa"],"appartement":["appart","f2","f3","f4","f5"],
    "terrain":["terrain","parcelle"],"duplex":["duplex"],
    "studio":["studio"],"maison":["maison"],"local":["local","commerce","bureau"],
    "chambre":["chambre","studio","f1"],
}
GREETINGS = {"bonjour","bonsoir","salut","hello","hi","coucou","bonne nuit",
             "merci","ok","oui","non","svp","s'il vous plait","stp"}
ANALYTIC_PATTERNS = [
    (r"(?:prix|valeur|cout|combien|que vaut|quel est le prix).{0,40}(?:moyen|median|typique|habituel)",
     "prix_stats"),
    (r"(?:que vaut|combien coute|quel est le prix).{0,50}(?:chambre|studio|villa|appart|terrain|duplex|maison)",
     "prix_stats"),
    (r"(?:prix|tarif|valeur).{0,30}(?:a|dans|au|en)\s+\w+",
     "prix_stats"),
    (r"(?:difference|comparer|comparaison|plus cher|moins cher|meilleur marche)",
     "comparaison"),
    (r"(?:quel|quelle).{0,20}(?:quartier|ville|zone).{0,20}(?:cher|abordable|moins cher|plus cher)",
     "comparaison"),
    (r"(?:statistique|tendance|marche immobilier|etat du marche|situation|apercu)",
     "stats_marche"),
    (r"(?:combien).{0,30}(?:annonce|bien|propriete|logement).{0,20}(?:disponible|en vente|a louer)",
     "stats_marche"),
    (r"(?:avec|pour|quel bien|que puis.je avoir|que peut.on trouver).{0,30}(?:budget|million|fcfa)",
     "budget_conseil"),
    (r"(?:budget de|avec \d+).{0,20}(?:fcfa|million)",
     "budget_conseil"),
    (r"(?:recommander|conseil|suggerer|meilleur|ideal).{0,50}(?:investir|acheter|louer|quartier)",
     "recommandation"),
    (r"(?:ou investir|ou acheter|ou louer|ou habiter|ou s.installer)",
     "recommandation"),
]


