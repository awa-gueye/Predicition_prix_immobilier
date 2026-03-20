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
    types  = ['Villa','Appartement','Terrain','Duplex','Studio','Maison','Local commercial']
    result = error = None; form = {}
    if request.method == 'POST':
        form = {k: request.POST.get(k,'') for k in
                ['city','property_type','surface_area','bedrooms','bathrooms']}
        try:
            sa = float(form['surface_area']) if form['surface_area'] else None
            bd = int(form['bedrooms'])       if form['bedrooms']     else 0
            bh = int(form['bathrooms'])      if form['bathrooms']    else 0
            result = _estimate(form['city'], form['property_type'], sa, bd, bh)
        except Exception as e:
            error = str(e)
    return render(request, 'immoanalytics/estimation.html',
                  _ctx(request, {'cities':cities,'types':types,
                                 'result':result,'error':error,'form':form}))

def _estimate(city, ptype, surface, bedrooms, bathrooms):
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
    try:
        from properties.models import CoinAfriqueProperty, ExpatDakarProperty
        from django.db.models import Avg
        prices = []
        for m in [CoinAfriqueProperty, ExpatDakarProperty]:
            qs = m.objects.filter(price__gt=0)
            if city:  qs = qs.filter(city__icontains=city)
            if ptype: qs = qs.filter(property_type__icontains=ptype)
            a = qs.aggregate(a=Avg('price'))['a']
            if a: prices.append(a)
        base = sum(prices)/len(prices) if prices else _zone_base(city)
    except:
        base = _zone_base(city)
    if surface and surface > 0: base = max(base, surface*450_000)
    base *= (1 + bedrooms*0.07)
    m = base*0.18
    return {'predicted_price':round(base),'price_min':round(base-m),
            'price_max':round(base+m),'model_used':'Estimation statistique','confidence':'±18%'}

def _zone_base(city):
    zones = {'almadies':240_000_000,'ngor':180_000_000,'ouakam':110_000_000,
             'mermoz':100_000_000,'plateau':80_000_000,'yoff':85_000_000,
             'pikine':28_000_000,'dakar':65_000_000,'thies':20_000_000}
    cl = (city or '').lower()
    return next((v for k,v in zones.items() if k in cl), 55_000_000)

def _get_cities():
    try:
        from properties.models import CoinAfriqueProperty
        cs = CoinAfriqueProperty.objects.values_list('city',flat=True).distinct().order_by('city')[:60]
        return sorted(set(c.strip() for c in cs if c and c.strip()))
    except:
        return ['Almadies','Dakar','Fann','Guediawaye','Mermoz','Ngor',
                'Ouakam','Pikine','Plateau','Rufisque','Thies','Yoff']

# ── Viewer + Chatbot ──────────────────────────────────────────────────────────
CITIES_SN = [
    "almadies","ngor","ouakam","mermoz","pikine","guediawaye","plateau","fann",
    "yoff","rufisque","liberte","hlm","sicap","grand yoff","keur massar",
    "medina","thies","mbour","dakar","parcelles","sacre coeur","vdn","saly",
    "patte d oie","dieuppeul","fass","colobane","biscuiterie","nord foire",
    "mbao","yeumbeul","keur ndiaye lo","diamniadio",
]
TYPE_MAP  = {"villa":["villa"],"appartement":["appart","f2","f3","f4","f5"],
             "terrain":["terrain","parcelle"],"duplex":["duplex"],
             "studio":["studio"],"maison":["maison"],"local":["local","commerce","bureau"]}
KW_LOC = ["louer","location","locat","bail","mensuel","loyer","à louer","a louer"]
KW_VTE = ["vendre","acheter","achat","vente","à vendre","a vendre"]

# Salutations et messages non-recherche
GREETINGS = ["bonjour","bonsoir","salut","hello","hi","coucou","bonne nuit","merci","ok","oui","non","svp"]
HELP_WORDS = ["aide","help","comment","quoi","que","quels","informations"]

PRICE_MIN = 1_000_000      # 1M FCFA minimum réaliste
PRICE_MAX = 5_000_000_000  # 5 milliards max


def _is_greeting(text: str) -> bool:
    tl = text.lower().strip().rstrip('!').rstrip('.').rstrip(',')
    return tl in GREETINGS or len(tl) < 4


def _amt(t):
    """Convertit un texte en montant FCFA."""
    try:
        s = str(t).replace(" ","").replace(",",".")
        v = float(s)
        # Détecter l'unité
        if v < 1_000:          # "150" → 150M
            return v * 1_000_000
        if v < 100_000:        # "150000" → déjà en FCFA si < 100K, sinon en FCFA brut
            # Ambiguïté : 150000 peut être 150 000 FCFA (trop bas) ou 150M (manque le M)
            # Règle : si < 500K → probablement une erreur, on ignore
            if v < 500:        return v * 1_000_000  # 150 → 150M
            return v           # 150000 → 150 000 FCFA (sera filtré si < PRICE_MIN)
        return v               # 150000000 → déjà en FCFA
    except:
        return None


def _parse(text: str) -> dict:
    """Extrait les critères de recherche depuis le texte naturel."""
    tl = (text.lower()
          .replace("é","e").replace("è","e").replace("à","a")
          .replace("ê","e").replace("â","a").replace("ô","o"))

    # Budget
    mn = mx = None

    # "entre X et Y"
    m = re.search(r"entre\s+([\d\s,.]+)\s*(?:m|milli|millions?|fcfa)?\s*(?:et|a|-)\s*([\d\s,.]+)\s*(?:m|milli|millions?|fcfa)?", tl)
    if m:
        mn, mx = _amt(m.group(1)), _amt(m.group(2))
    else:
        # "moins de X" / "max X" / "inferieur a X"
        m2 = re.search(r"(?:moins de|max|inferieur|jusqu'a|jusqu.a|pas plus de)\s+([\d\s,.]+)\s*(?:m|milli|millions?|fcfa|k)?", tl)
        if m2:
            raw = m2.group(1).strip()
            unit_after = m2.group(0).split(raw)[-1].strip()
            v = _amt(raw)
            if v: mx = v

        # "a partir de X" / "minimum X" / "plus de X"
        m3 = re.search(r"(?:a partir de|au moins|minimum|plus de|min)\s+([\d\s,.]+)\s*(?:m|milli|millions?|fcfa|k)?", tl)
        if m3:
            v = _amt(m3.group(1))
            if v: mn = v

        # Budget isolé : "X millions" / "XM" / "X M FCFA"
        if not mx and not mn:
            m4 = re.search(r"([\d]+(?:[.,][\d]+)?)\s*(?:m|millions?|mds)", tl)
            if m4:
                v = _amt(m4.group(1))
                if v and v >= PRICE_MIN:
                    mn = v * 0.7
                    mx = v * 1.4

        # Montant brut en FCFA style "150000 fcfa" ou "2000000"
        if not mx and not mn:
            m5 = re.search(r"([\d]{4,})\s*(?:fcfa|f)?", tl)
            if m5:
                v = float(m5.group(1).replace(" ",""))
                if v >= PRICE_MIN:
                    mn = v * 0.7
                    mx = v * 1.4

    # Valider les montants (rejeter si trop bas)
    if mn and mn < PRICE_MIN: mn = None
    if mx and mx < PRICE_MIN: mx = None

    # Ville
    city = next((c.title() for c in sorted(CITIES_SN, key=len, reverse=True) if c in tl), None)

    # Type de bien
    ptype = next((k.capitalize() for k, kws in TYPE_MAP.items()
                  if any(w in tl for w in [k]+kws)), None)

    # Transaction
    txn = ("location" if any(k in tl for k in KW_LOC)
           else "vente" if any(k in tl for k in KW_VTE)
           else None)

    # Chambres
    beds = None
    mb = re.search(r"(\d+)\s*chambre", tl)
    if mb: beds = int(mb.group(1))
    mb2 = re.search(r"f(\d)", tl)
    if mb2: beds = max(1, int(mb2.group(1)) - 1)

    return {"city": city, "type": ptype, "transaction": txn,
            "min_price": mn, "max_price": mx, "bedrooms": beds}


def _search(crit: dict):
    """Recherche dans toutes les tables avec filtres sur prix valides."""
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty)
        MODELS = [
            (CoinAfriqueProperty, 'coinafrique'),
            (ExpatDakarProperty,  'expat_dakar'),
            (LogerDakarProperty,  'loger_dakar'),
            (DakarVenteProperty,  'dakarvente'),
            (ImmoSenegalProperty, 'immosenegal'),
        ]
        results = []
        for model, src in MODELS:
            qs = model.objects.filter(price__gte=PRICE_MIN, price__lte=PRICE_MAX)
            if crit.get('city'):
                qs = qs.filter(city__icontains=crit['city'])
            if crit.get('type'):
                qs = qs.filter(property_type__icontains=crit['type'])
            if crit.get('min_price'):
                qs = qs.filter(price__gte=max(crit['min_price'], PRICE_MIN))
            if crit.get('max_price'):
                qs = qs.filter(price__lte=crit['max_price'])
            if crit.get('bedrooms'):
                qs = qs.filter(bedrooms__gte=crit['bedrooms'])

            for p in qs.order_by('price').values(
                'id', 'title', 'price', 'city', 'property_type',
                'surface_area', 'bedrooms', 'url')[:80]:
                results.append({**p, 'source': src})

        # Dédoublonnage + tri
        seen, deduped = set(), []
        for r in sorted(results, key=lambda x: x.get('price') or 0):
            key = (r.get('price'), str(r.get('city', ''))[:8], str(r.get('property_type', ''))[:8])
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        return deduped, len(deduped)
    except Exception as e:
        logger.warning(f"Search error: {e}")
        return [], 0


def _fmt_price(price) -> str:
    """Formate un prix de façon lisible en FCFA."""
    if not price:
        return "—"
    try:
        p = float(price)
        if p < PRICE_MIN:      return "—"
        if p >= 1_000_000_000: return f"{p/1_000_000_000:.2f} Mds FCFA"
        if p >= 1_000_000:     return f"{p/1_000_000:.1f}M FCFA"
        if p >= 1_000:         return f"{p/1_000:.0f}K FCFA"
        return f"{p:,.0f} FCFA"
    except:
        return "—"


@login_required(login_url='/immo/login/')
def api_chatbot(request):
    """Endpoint AJAX pour le chatbot IA."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST requis'}, status=405)
    try:
        body = json.loads(request.body)
        q    = body.get('message', '').strip()
        if not q:
            return JsonResponse({'error': 'Message vide'}, status=400)

        # ── Détecter les messages hors-recherche ─────────────────────────────
        if _is_greeting(q):
            greet_resp = (
                "Bonjour ! Je suis votre assistant immobilier. "
                "Décrivez le bien que vous recherchez.<br>"
                "<small style='opacity:.6'>Exemple : <em>villa Almadies moins de 200M</em> "
                "ou <em>appartement 3 chambres Ouakam location</em></small>"
            )
            return JsonResponse({'response': greet_resp, 'total': 0, 'properties': []})

        # Détecter demande d'aide
        tl = q.lower()
        if any(w in tl for w in HELP_WORDS) and len(tl) < 30:
            help_resp = (
                "Je peux vous aider à trouver des biens immobiliers. Précisez :<br>"
                "• <b>Type</b> : villa, appartement, terrain, studio…<br>"
                "• <b>Localité</b> : Almadies, Ouakam, Dakar, Pikine…<br>"
                "• <b>Budget</b> : moins de 100M, entre 50M et 150M…<br>"
                "• <b>Transaction</b> : vente ou location<br>"
                "<em>Ex : studio à louer Plateau moins de 300K/mois</em>"
            )
            return JsonResponse({'response': help_resp, 'total': 0, 'properties': []})

        # ── Extraction des critères et recherche ─────────────────────────────
        crit    = _parse(q)
        has_criteria = any(crit.get(k) for k in ['city','type','transaction','min_price','max_price','bedrooms'])

        if not has_criteria:
            no_crit_resp = (
                "Je n'ai pas bien compris votre recherche. "
                "Essayez par exemple :<br>"
                "• <em>Villa à vendre à Almadies moins de 300M</em><br>"
                "• <em>Appartement 3 chambres location Ouakam</em><br>"
                "• <em>Terrain Pikine entre 10M et 30M</em>"
            )
            return JsonResponse({'response': no_crit_resp, 'total': 0, 'properties': []})

        results, total = _search(crit)

        # ── Réponse naturelle ─────────────────────────────────────────────────
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
            lines.append(
                "Aucun bien trouvé pour ces critères.<br>"
                "<small style='opacity:.65'>Suggestions : essayez un quartier différent, "
                "élargissez votre budget, ou retirez certains filtres.</small>"
            )
        elif total == 1:
            prices = [r['price'] for r in results if r.get('price') and r['price'] >= PRICE_MIN]
            lines.append(f"<b>1</b> bien trouvé au prix de <b>{_fmt_price(prices[0]) if prices else '—'}</b>.")
        else:
            lines.append(f"<b>{total}</b> biens trouvés.")
            prices = sorted([r['price'] for r in results if r.get('price') and r['price'] >= PRICE_MIN])
            if len(prices) >= 2:
                lines.append(
                    f"Prix : de <b>{_fmt_price(prices[0])}</b> "
                    f"à <b>{_fmt_price(prices[-1])}</b>."
                )

        props = []
        for p in results[:6]:
            price = p.get('price') or 0
            if price < PRICE_MIN:
                continue
            props.append({
                'title':     str(p.get('title', '') or 'Annonce immobilière')[:60],
                'price':     price,
                'price_fmt': _fmt_price(price),
                'city':      str(p.get('city', '') or ''),
                'type':      str(p.get('property_type', '') or ''),
                'source':    p.get('source', ''),
                'surface':   p.get('surface_area', ''),
                'bedrooms':  p.get('bedrooms', ''),
            })

        return JsonResponse({
            'response':   " ".join(lines),
            'total':      total,
            'properties': props,
        })

    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        return JsonResponse({'response': "Une erreur s'est produite. Réessayez.", 'total': 0, 'properties': []})



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

