"""
ImmoPredict SN — views.py
Toutes les vues Django (sans chatbot, déplacé dans chatbot_groq.py).
"""
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
            error = "Tous les champs obligatoires doivent être remplis."
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
            'Données réelles de 5 sources agrégées',
            'Prédiction ML des prix (XGBoost)',
            'Chatbot ImmoAI propulsé par Groq',
            'Carte interactive des annonces',
        ]
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
    return render(request, 'immoanalytics/profile.html', _ctx(request))


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
            u.save(); messages.success(request, "Profil mis à jour.")
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


# ── Dashboard pages via chart_views ──────────────────────────────────────────
# (dashboard_page et analytics_page sont dans chart_views.py)


# ── Admin Panel ───────────────────────────────────────────────────────────────
@login_required(login_url='/immo/login/')
def admin_panel_page(request):
    if not request.user.is_superuser:
        return redirect('/viewer/')
    return render(request, 'immoanalytics/dash_page.html', _ctx(request, {
        'page_title': 'Admin Panel', 'dash_app_id': 'AdminPanel',
    }))


# ── Carte géographique ────────────────────────────────────────────────────────
PRICE_MIN = 500_000

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
                latitude__isnull=False, longitude__isnull=False, price__gte=PRICE_MIN
            ).values('title','price','city','property_type','latitude','longitude')[:600]:
                lat, lon = float(p['latitude'] or 0), float(p['longitude'] or 0)
                if 12 < lat < 17 and -18 < lon < -14:
                    props.append({'t':str(p.get('title','') or '')[:50],
                                  'p':int(p['price'] or 0),
                                  'c':str(p.get('city','') or ''),
                                  'k':str(p.get('property_type','') or ''),
                                  'lat':round(lat,5),'lon':round(lon,5),'s':src})
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


# ── Estimation ────────────────────────────────────────────────────────────────
PRIX_REF = {
    ("chambre","location"):     (30_000,    70_000,   150_000),
    ("studio","location"):      (60_000,   120_000,   300_000),
    ("appartement","location"): (150_000,  400_000, 1_500_000),
    ("villa","location"):       (300_000,1_200_000, 5_000_000),
    ("duplex","location"):      (250_000,  800_000, 3_000_000),
    ("maison","location"):       (80_000,  250_000,   800_000),
    ("chambre","vente"):      (500_000,  2_000_000,  8_000_000),
    ("studio","vente"):     (2_000_000,  8_000_000, 25_000_000),
    ("appartement","vente"):(8_000_000, 40_000_000,200_000_000),
    ("villa","vente"):     (20_000_000,100_000_000,500_000_000),
    ("duplex","vente"):    (15_000_000, 70_000_000,300_000_000),
    ("terrain","vente"):    (2_000_000, 20_000_000,300_000_000),
    ("maison","vente"):     (5_000_000, 30_000_000,150_000_000),
    ("local","vente"):     (10_000_000, 50_000_000,300_000_000),
}
ZONE_MULT = {
    "almadies":3.5,"ngor":3.0,"mermoz":2.5,"ouakam":2.0,"fann":2.2,
    "plateau":2.0,"yoff":1.8,"sacre coeur":2.3,"vdn":1.9,"point e":2.1,
    "sicap":1.5,"liberte":1.5,"hlm":1.3,"pikine":0.7,"guediawaye":0.65,
    "rufisque":0.55,"thies":0.5,"mbour":0.6,"saly":1.2,"dakar":1.0,
}


@login_required(login_url='/immo/login/')
def estimation_page(request):
    cities = _get_cities()
    types  = ['Villa','Appartement','Terrain','Duplex','Studio','Maison','Chambre','Local commercial','Bureau']
    transactions = [('vente','Achat / Vente'),('location','Location mensuelle')]
    result = error = None; form = {}

    if request.method == 'POST':
        form = {k: request.POST.get(k,'') for k in
                ['city','property_type','surface_area','bedrooms','bathrooms','transaction']}
        try:
            sa  = float(form['surface_area']) if form['surface_area'] else None
            bd  = int(form['bedrooms'])        if form['bedrooms']     else 0
            bh  = int(form['bathrooms'])       if form['bathrooms']    else 0
            txn = form.get('transaction','vente') or 'vente'
            result = _estimate(form['city'], form['property_type'], sa, bd, bh, txn)
        except Exception as e:
            error = str(e)

    return render(request, 'immoanalytics/estimation.html', _ctx(request, {
        'cities': cities, 'types': types,
        'transactions': transactions,
        'result': result, 'error': error, 'form': form,
    }))


def _fmt_price(p):
    if not p or float(p) < 100: return "—"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _normalize_type(ptype):
    if not ptype: return "appartement"
    tl = ptype.lower()
    mapping = [("chambre",["chambre","room"]),("studio",["studio","f1","t1"]),
               ("villa",["villa","maison individuelle"]),("appartement",["appart","f2","f3","f4","f5"]),
               ("terrain",["terrain","parcelle","lot"]),("duplex",["duplex","triplex"]),
               ("maison",["maison","bungalow"]),("local",["bureau","local","commerce"])]
    for key, kws in mapping:
        if any(w in tl for w in [key]+kws): return key
    return tl.split()[0] if tl else "appartement"


def _estimate(city, ptype, surface, bedrooms, bathrooms, transaction="vente"):
    import os, sys, importlib
    ml_dir = os.path.normpath(os.path.join(os.path.dirname(__file__),'..','properties','ml'))
    if os.path.exists(os.path.join(ml_dir,'predict.py')):
        if ml_dir not in sys.path: sys.path.insert(0, ml_dir)
        try:
            mod = importlib.import_module('predict')
            return mod.predict_price(city=city, property_type=ptype,
                surface_area=surface, bedrooms=bedrooms, bathrooms=bathrooms)
        except Exception as e:
            logger.warning(f"ML: {e}")

    type_key = _normalize_type(ptype)
    txn      = transaction or "vente"

    # Chercher dans DB
    try:
        from properties.models import CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty
        from django.db.models import Avg
        import statistics as st
        prices = []
        for model in [CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty]:
            qs = model.objects.filter(price__gte=10_000, price__lt=5_000_000_000)
            if city:  qs = qs.filter(city__icontains=city[:6])
            if ptype: qs = qs.filter(property_type__icontains=type_key[:5])
            batch = list(qs.values_list("price", flat=True)[:200])
            prices.extend([float(p) for p in batch if p])
        base = st.median(prices) if len(prices) >= 5 else None
    except: base = None

    if not base:
        ref = PRIX_REF.get((type_key, txn))
        if not ref:
            for k, v in PRIX_REF.items():
                if k[0] == type_key: ref = v; break
        if not ref: ref = PRIX_REF.get(("appartement", txn), (1_000_000, 30_000_000, 100_000_000))
        base = ref[1]

    # Zone
    city_key = (city or "dakar").lower().strip()
    mult = next((v for k, v in ZONE_MULT.items() if k in city_key), 1.0)
    base *= mult

    # Surface
    if surface and surface > 0 and type_key not in ("chambre","terrain"):
        pm2 = {"appartement":400_000,"villa":600_000,"duplex":500_000,"studio":450_000}.get(type_key, 350_000)
        if txn == "location": pm2 = pm2 // 180
        base = base * 0.4 + (surface * pm2 * mult) * 0.6

    if bedrooms and bedrooms > 1 and type_key not in ("chambre","studio","terrain"):
        base *= (1 + (bedrooms - 1) * 0.05)

    base   = max(base, 10_000)
    margin = base * 0.20
    unit   = "/mois" if txn == "location" else ""

    return {
        'predicted_price': round(base),
        'price_min':       round(max(base - margin, 10_000)),
        'price_max':       round(base + margin),
        'model_used':      f"Estimation statistique — {type_key} en {txn}",
        'confidence':      '±20%',
        'transaction':     txn,
        'unit':            unit,
    }


def _get_cities():
    """Charge les villes depuis toutes les sources DB avec fallback complet."""
    FALLBACK = [
        "Almadies","Dakar","Dieuppeul","Fann","Grand Yoff","Guediawaye",
        "HLM","Hann","Keur Massar","Liberte","Mbao","Mbour","Medina",
        "Mermoz","Ngor","Nord Foire","Ouakam","Parcelles Assainies","Patte d'Oie",
        "Pikine","Plateau","Rufisque","Sacre-Coeur","Saly","Sicap","Thies",
        "Thiaroye","VDN","Yeumbeul","Yoff","Diamniadio","Bargny","Kaolack",
        "Saint-Louis","Ziguinchor","Touba","Biscuiterie",
    ]
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        cities = set()
        for model in [CoinAfriqueProperty, ExpatDakarProperty,
                      LogerDakarProperty, DakarVenteProperty]:
            try:
                for c in model.objects.values_list("city", flat=True).distinct()[:80]:
                    if c and c.strip():
                        city = c.strip().split(",")[0].strip().title()
                        if city and len(city) > 1:
                            cities.add(city)
            except: pass
        result = sorted(cities)
        return result if len(result) >= 5 else sorted(FALLBACK)
    except:
        return sorted(FALLBACK)


# ── Viewer ────────────────────────────────────────────────────────────────────
CITIES_SN = ["almadies","ngor","ouakam","mermoz","pikine","guediawaye","plateau","fann",
             "yoff","rufisque","liberte","hlm","sicap","grand yoff","keur massar",
             "medina","thies","mbour","dakar","parcelles","vdn","saly","diamniadio"]
TYPE_MAP  = {"villa":["villa"],"appartement":["appart","f2","f3","f4","f5"],
             "terrain":["terrain","parcelle"],"duplex":["duplex"],"studio":["studio"],
             "maison":["maison"],"local":["local","commerce","bureau"],"chambre":["chambre"]}
KW_LOC = ["louer","location","locat","bail","mensuel","loyer"]
KW_VTE = ["vendre","acheter","achat","vente"]


def _parse(text):
    tl = (text.lower()
          .replace("é","e").replace("è","e").replace("à","a")
          .replace("ê","e").replace("â","a").replace("ç","c"))
    mn = mx = None
    NB  = r"([\d][\d\s]*(?:[.,][\d]+)?)"
    UNI = r"\s*(m\b|millions?|mds|milliard|k\b|mille|fcfa|cfa)?"
    m = re.search(r"entre\s+" + NB + UNI + r"\s*(?:et|-)\s*" + NB + UNI, tl)
    if m:
        mn = _amt(m.group(1).replace(" ",""), m.group(2) or "")
        mx = _amt(m.group(3).replace(" ",""), m.group(4) or "")
    else:
        m2 = re.search(r"(?:moins de|max|pas plus de)\s+" + NB + UNI, tl)
        if m2: mx = _amt(m2.group(1).replace(" ",""), m2.group(2) or "")
        m3 = re.search(r"(?:a partir de|au moins|plus de)\s+" + NB + UNI, tl)
        if m3: mn = _amt(m3.group(1).replace(" ",""), m3.group(2) or "")
        if not m2 and not m3:
            m4 = re.search(NB + r"\s*(m\b|millions?|mds|milliard)", tl)
            if m4:
                v = _amt(m4.group(1).replace(" ",""), m4.group(2))
                if v: mn = v*0.7; mx = v*1.4
            if not mx and not mn:
                m5 = re.search(r"([\d]{4,})\s*(?:fcfa|cfa)?", tl)
                if m5:
                    v = _amt(m5.group(1))
                    if v: mn = v*0.7; mx = v*1.4
    if mn and mn <= 0: mn = None
    if mx and mx <= 0: mx = None
    city  = next((c.title() for c in sorted(CITIES_SN, key=len, reverse=True) if c in tl), None)
    ptype = next((k.capitalize() for k, kws in TYPE_MAP.items() if any(w in tl for w in [k]+kws)), None)
    txn   = ("location" if any(k in tl for k in KW_LOC) else "vente" if any(k in tl for k in KW_VTE) else None)
    beds  = None
    mb = re.search(r"(\d+)\s*chambre", tl)
    if mb: beds = int(mb.group(1))
    mb2 = re.search(r"\bf(\d)\b", tl)
    if mb2: beds = max(1, int(mb2.group(1))-1)
    return {"city":city,"type":ptype,"transaction":txn,"min_price":mn,"max_price":mx,"bedrooms":beds}


def _amt(t, unit=""):
    try:
        v = float(str(t).replace(" ","").replace(",","."))
        if v <= 0: return None
        u = (unit or "").lower().strip()
        if u in ("m","million","millions"): return v * 1_000_000
        if u in ("mds","milliard"):         return v * 1_000_000_000
        if u in ("k","mille"):              return v * 1_000
        if v < 1_000: return v * 1_000_000
        return v
    except: return None


def _search(crit):
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty)
        MODELS = [(CoinAfriqueProperty,"coinafrique"),(ExpatDakarProperty,"expat_dakar"),
                  (LogerDakarProperty,"loger_dakar"),(DakarVenteProperty,"dakarvente"),
                  (ImmoSenegalProperty,"immosenegal")]
        results = []
        for model, src in MODELS:
            qs = model.objects.filter(price__gte=10_000, price__lte=5_000_000_000)
            if crit.get("city"):      qs = qs.filter(city__icontains=crit["city"])
            if crit.get("type"):      qs = qs.filter(property_type__icontains=crit["type"])
            if crit.get("min_price"): qs = qs.filter(price__gte=crit["min_price"])
            if crit.get("max_price"): qs = qs.filter(price__lte=crit["max_price"])
            if crit.get("bedrooms"):  qs = qs.filter(bedrooms__gte=crit["bedrooms"])
            for p in qs.order_by("price").values(
                "id","title","price","city","property_type","surface_area","bedrooms","url")[:80]:
                results.append({**p,"source":src})
        seen, deduped = set(), []
        for r in sorted(results, key=lambda x: x.get("price") or 0):
            key = (r.get("price"), str(r.get("city",""))[:8])
            if key not in seen:
                seen.add(key); deduped.append(r)
        return deduped, len(deduped)
    except Exception as e:
        logger.warning(f"Search: {e}")
        return [], 0


@login_required(login_url='/immo/login/')
def viewer_page(request):
    q     = request.GET.get('q','')
    city  = request.GET.get('city','')
    ptype = request.GET.get('type','')
    txn   = request.GET.get('txn','')
    min_p = request.GET.get('min_price','')
    max_p = request.GET.get('max_price','')
    min_b = request.GET.get('beds','')
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
        'q':q, 'results':results[:24], 'total':total, 'ai_msg':ai_msg,
        'cities':_get_cities(), 'city':city, 'ptype':ptype, 'txn':txn,
        'min_p':min_p, 'max_p':max_p, 'min_b':min_b,
        'prop_types':   ['Villa','Appartement','Terrain','Duplex','Studio','Maison','Chambre'],
        'beds_choices': ['1','2','3','4','5'],
    }))


# ── About & Contact ───────────────────────────────────────────────────────────
def about_view(request):
    technologies = [
        {"name":"Django 6",          "desc":"Framework web Python",          "icon":"fab fa-python"},
        {"name":"PostgreSQL / Neon",  "desc":"Base de données cloud",         "icon":"fas fa-database"},
        {"name":"XGBoost / LightGBM", "desc":"Modèles ML de prédiction",      "icon":"fas fa-brain"},
        {"name":"Groq API",           "desc":"LLM llama-3.3-70b",             "icon":"fas fa-robot"},
        {"name":"Scrapy",             "desc":"Scraping des annonces",         "icon":"fas fa-spider"},
        {"name":"Plotly.js",          "desc":"Visualisations interactives",    "icon":"fas fa-chart-bar"},
        {"name":"Leaflet.js",         "desc":"Carte interactive",              "icon":"fas fa-map"},
        {"name":"Render / GitHub",    "desc":"Déploiement cloud",             "icon":"fas fa-cloud"},
    ]
    data_sources = [
        {"name":"CoinAfrique",   "desc":"Plateforme panafricaine",     "color":"#F59E0B", "count":"~3000 annonces"},
        {"name":"Expat-Dakar",   "desc":"Annonces expatriés",          "color":"#2563EB", "count":"~2000 annonces"},
        {"name":"Loger-Dakar",   "desc":"Spécialiste Dakar",           "color":"#0E6B4A", "count":"~1500 annonces"},
        {"name":"DakarVente",    "desc":"Ventes immobilières",         "color":"#C0392B", "count":"~2500 annonces"},
        {"name":"2simmobilier",  "desc":"Nouveau scraper intégré",     "color":"#0891B2", "count":"En cours"},
    ]
    # Stats réelles
    stats_data = []
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty)
        total = sum(m.objects.count() for m in [
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty])
        stats_data = [
            {"label":"Annonces indexées",   "value":f"{total:,}"},
            {"label":"Sources de données",  "value":"5"},
            {"label":"Quartiers couverts",  "value":"80+"},
            {"label":"Modèle ML",           "value":"XGBoost"},
        ]
    except:
        stats_data = [
            {"label":"Annonces indexées",   "value":"10K+"},
            {"label":"Sources de données",  "value":"5"},
            {"label":"Quartiers couverts",  "value":"80+"},
            {"label":"Modèle ML",           "value":"XGBoost"},
        ]

    ctx = {}
    if request.user.is_authenticated:
        ctx = _ctx(request)
        return render(request, 'immoanalytics/about.html', {
            **ctx, 'technologies':technologies, 'data_sources':data_sources, 'stats':stats_data,
        })
    return render(request, 'immoanalytics/about_public.html', {
        'technologies':technologies, 'data_sources':data_sources, 'stats':stats_data,
    })


def contact_view(request):
    sent = error = None
    ctx = {}
    if request.user.is_authenticated:
        ctx = _ctx(request)

    contacts = [
        {"icon":"fas fa-envelope",  "label":"Email",      "value":"contact@immopredict.sn"},
        {"icon":"fas fa-phone",     "label":"Téléphone",  "value":"+221 XX XXX XX XX"},
        {"icon":"fas fa-map-pin",   "label":"Adresse",    "value":"Dakar, Sénégal"},
        {"icon":"fab fa-linkedin",  "label":"LinkedIn",   "value":"ImmoPredict SN"},
    ]

    if request.method == 'POST':
        fname   = request.POST.get('first_name','').strip()
        email   = request.POST.get('email','').strip()
        subject = request.POST.get('subject','')
        msg_txt = request.POST.get('message','').strip()
        if not fname or not email or not msg_txt:
            error = "Veuillez remplir tous les champs obligatoires."
        else:
            sent = True  # En production : envoyer un email via Django

    template = 'immoanalytics/contact.html' if request.user.is_authenticated else 'immoanalytics/contact_public.html'
    return render(request, template, {**ctx, 'sent':sent, 'error':error, 'contacts':contacts})


# ── API ───────────────────────────────────────────────────────────────────────
def api_current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated':False}, status=401)
    u = request.user; fn = u.get_full_name() or u.username
    return JsonResponse({'authenticated':True,'username':u.username,'full_name':fn,
                         'role':get_user_role(u),'initials':''.join(p[0].upper() for p in fn.split()[:2])})


def api_check_auth(request):
    if request.user.is_authenticated:
        return JsonResponse({'authenticated':True,'role':get_user_role(request.user)})
    return JsonResponse({'authenticated':False}, status=401)
