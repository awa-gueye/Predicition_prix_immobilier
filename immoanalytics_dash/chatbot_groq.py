"""
ImmoPredict SN — chatbot_groq.py
Chatbot ImmoAI : assistant polyvalent propulse par Groq (llama-3.3-70b-versatile).
Repond a TOUTE question : immobilier, culture generale, calculs, conseils, etc.
Fallback local intelligent si Groq est indisponible.
"""
import re, json, logging, os, math
import statistics as stats
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)

PRICE_MIN = 500_000
PRICE_MAX = 5_000_000_000
GROQ_MODEL = "llama-3.3-70b-versatile"

CITIES_SN = [
    "almadies","ngor","ouakam","mermoz","pikine","guediawaye","plateau","fann",
    "yoff","rufisque","liberte","hlm","sicap","grand yoff","keur massar",
    "medina","thies","mbour","dakar","parcelles","sacre coeur","vdn","saly",
    "patte d oie","dieuppeul","fass","colobane","hann","diamniadio","bargny",
    "nord foire","point e","mamelles","cite keur gorgui","liberté 6",
]
TYPE_MAP = {
    "villa":       ["villa"],
    "appartement": ["appart","f2","f3","f4","f5"],
    "terrain":     ["terrain","parcelle","lot"],
    "duplex":      ["duplex","triplex"],
    "studio":      ["studio","f1","t1"],
    "maison":      ["maison","bungalow"],
    "local":       ["local","commerce","bureau","boutique"],
    "chambre":     ["chambre","room","piece"],
    "immeuble":    ["immeuble","building","r+"],
}
KW_LOC = ["louer","location","locat","bail","mensuel","loyer","a louer","rent"]
KW_VTE = ["vendre","acheter","achat","vente","a vendre","buy","purchase"]

GREETINGS = {
    "bonjour","bonsoir","salut","hello","hi","hey","coucou","bonne nuit",
    "merci","thanks","ok","oui","non","svp","stp","yo","wesh",
    "ca va","comment ca va","quoi de neuf","cc",
}

# Prix de reference par type et transaction
PRIX_REF = {
    ("chambre","location"):     (30_000, 70_000, 150_000),
    ("studio","location"):      (60_000, 120_000, 300_000),
    ("appartement","location"): (150_000, 400_000, 1_500_000),
    ("villa","location"):       (300_000, 1_200_000, 5_000_000),
    ("chambre","vente"):        (500_000, 2_000_000, 8_000_000),
    ("studio","vente"):         (2_000_000, 8_000_000, 25_000_000),
    ("appartement","vente"):    (8_000_000, 40_000_000, 200_000_000),
    ("villa","vente"):          (20_000_000, 100_000_000, 500_000_000),
    ("terrain","vente"):        (2_000_000, 20_000_000, 300_000_000),
    ("maison","vente"):         (5_000_000, 30_000_000, 150_000_000),
    ("duplex","vente"):         (15_000_000, 70_000_000, 300_000_000),
    ("immeuble","vente"):       (50_000_000, 200_000_000, 2_000_000_000),
}

ZONE_MULT = {
    "almadies":3.5,"ngor":3.0,"mermoz":2.5,"ouakam":2.0,"fann":2.2,
    "plateau":2.0,"yoff":1.8,"sacre coeur":2.3,"vdn":1.9,"point e":2.1,
    "mamelles":2.8,"cite keur gorgui":2.0,"nord foire":1.7,
    "sicap":1.5,"liberte":1.5,"hlm":1.3,"pikine":0.7,"guediawaye":0.65,
    "rufisque":0.55,"thies":0.5,"mbour":0.6,"saly":1.2,"dakar":1.0,
    "keur massar":0.6,"diamniadio":0.7,"parcelles":0.8,"medina":1.1,
}

# ── Patterns d'intention enrichis ────────────────────────────────────────────

INTENT_PATTERNS = [
    # Immobilier
    (r"(?:prix|valeur|cout|combien|que vaut|quel est le prix|estime)", "prix_stats"),
    (r"(?:difference|comparer|plus cher|moins cher|abordable|meilleur marche)", "comparaison"),
    (r"(?:statistique|tendance|marche|etat du marche|apercu|situation|resume)", "stats_marche"),
    (r"(?:budget|million|fcfa|avec \d|que puis.je|que peut.on)", "budget_conseil"),
    (r"(?:recommand|conseil|meilleur|ideal|ou investir|ou acheter|ou louer|ou habiter)", "recommandation"),
    (r"(?:recent|nouveau|dernier|latest|derniere annonce)", "recents"),
    (r"(?:proximite|pres de|a cote|proche|nearby|autour)", "proximite"),
    # Calculs financiers
    (r"(?:rentabilite|rendement|roi|retour|rapport)", "calcul_rentabilite"),
    (r"(?:mensualite|credit|emprunt|pret|mortgage|remboursement)", "calcul_mensualite"),
    (r"(?:frais|notaire|taxe|impot|fiscal)", "frais_notaire"),
    # Informations pratiques
    (r"(?:demarche|procedure|etape|comment acheter|comment louer|comment vendre)", "demarches"),
    (r"(?:quartier|ville|zone).{0,30}(?:securite|calme|famille|commerce|transport)", "info_quartier"),
    (r"(?:surface|m2|metre carre|taille|superficie)", "info_surface"),
]


# ── Fonctions utilitaires ────────────────────────────────────────────────────

def _fmt(p):
    if not p or float(p) < 100: return "—"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _is_greeting(text):
    tl = text.lower().strip().rstrip("!?.,;:")
    return tl in GREETINGS or len(tl.replace(" ","")) < 4


def _normalize(text):
    return (text.lower()
            .replace("é","e").replace("è","e").replace("ê","e")
            .replace("à","a").replace("â","a").replace("ç","c")
            .replace("ô","o").replace("î","i").replace("ù","u")
            .replace("'","'").replace("\u2019","'"))


def _detect_intent(text):
    tl = _normalize(text)
    for pattern, intent in INTENT_PATTERNS:
        if re.search(pattern, tl):
            return intent
    return "general"


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


def _parse(text):
    tl = _normalize(text)
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
                if v: mn = v*0.7; mx = v*1.4
            if not mx and not mn:
                m5 = re.search(r"([\d]{6,})\s*(?:fcfa|cfa)?", tl)
                if m5:
                    v = _amt(m5.group(1))
                    if v: mn = v*0.7; mx = v*1.4

    if mn and mn <= 0: mn = None
    if mx and mx <= 0: mx = None

    city = next((c.title() for c in sorted(CITIES_SN, key=len, reverse=True) if c in tl), None)
    ptype = next((k.capitalize() for k, kws in TYPE_MAP.items() if any(w in tl for w in [k]+kws)), None)
    txn = ("location" if any(k in tl for k in KW_LOC)
           else "vente" if any(k in tl for k in KW_VTE)
           else None)
    beds = None
    mb = re.search(r"(\d+)\s*chambre", tl)
    if mb: beds = int(mb.group(1))
    mb2 = re.search(r"\bf(\d)\b", tl)
    if mb2: beds = max(1, int(mb2.group(1))-1)

    return {"city":city, "type":ptype, "transaction":txn,
            "min_price":mn, "max_price":mx, "bedrooms":beds}


def _extract_numbers(text):
    """Extrait tous les nombres du texte."""
    nums = re.findall(r"[\d]+(?:[.,]\d+)?", text.replace(" ",""))
    return [float(n.replace(",",".")) for n in nums if n]


# ── Acces aux donnees ────────────────────────────────────────────────────────

def _get_db_data():
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        MODELS = [CoinAfriqueProperty, ExpatDakarProperty,
                  LogerDakarProperty, DakarVenteProperty]
        results = []
        for model in MODELS:
            try:
                avail = [f.name for f in model._meta.get_fields()]
                fields = [f for f in ["price","city","property_type","surface_area",
                                      "bedrooms","statut","title"] if f in avail]
                for p in model.objects.filter(
                    price__gte=PRICE_MIN, price__lte=PRICE_MAX
                ).values(*fields)[:2000]:
                    results.append(p)
            except:
                continue
        return results
    except Exception as e:
        logger.warning(f"DB: {e}")
        return []


def _search(crit):
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        MODELS = [(CoinAfriqueProperty,"coinafrique"),(ExpatDakarProperty,"expat_dakar"),
                  (LogerDakarProperty,"loger_dakar"),(DakarVenteProperty,"dakarvente")]
        results = []
        for model, src in MODELS:
            qs = model.objects.filter(price__gte=PRICE_MIN, price__lte=PRICE_MAX)
            if crit.get("city"):      qs = qs.filter(city__icontains=crit["city"])
            if crit.get("type"):      qs = qs.filter(property_type__icontains=crit["type"])
            if crit.get("min_price"): qs = qs.filter(price__gte=crit["min_price"])
            if crit.get("max_price"): qs = qs.filter(price__lte=crit["max_price"])
            if crit.get("bedrooms"):  qs = qs.filter(bedrooms__gte=crit["bedrooms"])
            for p in qs.order_by("price").values(
                "id","title","price","city","property_type","surface_area","bedrooms","url")[:60]:
                results.append({**p, "source": src})
        seen, deduped = set(), []
        for r in sorted(results, key=lambda x: x.get("price") or 0):
            key = (r.get("price"), str(r.get("city",""))[:8])
            if key not in seen:
                seen.add(key); deduped.append(r)
        return deduped, len(deduped)
    except Exception as e:
        logger.warning(f"Search: {e}")
        return [], 0


def _make_props(results, limit=6):
    return [{"title":str(p.get("title","") or "")[:50],
             "price":p.get("price",0),
             "price_fmt":_fmt(p.get("price",0)),
             "city":str(p.get("city","") or ""),
             "type":str(p.get("property_type","") or ""),
             "source":p.get("source",""),
             "surface":p.get("surface_area",""),
             "bedrooms":p.get("bedrooms","")} for p in results[:limit]]


# ── Contexte marche pour Groq ────────────────────────────────────────────────

def _build_context():
    data = _get_db_data()
    if not data:
        return "Base de donnees: aucune donnee disponible actuellement."

    prices = [float(d["price"]) for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if not prices:
        return "Donnees de prix insuffisantes."

    types = Counter(str(d.get("property_type","") or "").strip() for d in data)
    cities_prices = {}
    for d in data:
        c = str(d.get("city","") or "").strip().title()
        if c and c != "Inconnu" and d.get("price"):
            cities_prices.setdefault(c, []).append(float(d["price"]))

    top_cities = sorted(
        [(c, stats.median(ps), len(ps)) for c, ps in cities_prices.items() if len(ps) >= 5],
        key=lambda x: x[1], reverse=True
    )[:10]

    ctx = f"""DONNEES DU MARCHE IMMOBILIER SENEGALAIS (donnees reelles ImmoPredict SN):
- Total annonces indexees: {len(data):,}
- Prix median global: {_fmt(stats.median(prices))}
- Prix moyen global: {_fmt(stats.mean(prices))}
- Fourchette: {_fmt(min(prices))} - {_fmt(max(prices))}

TYPES DE BIENS (top 6):
{chr(10).join(f"- {t}: {n} annonces" for t,n in types.most_common(6))}

PRIX MEDIANS PAR QUARTIER (top 10):
{chr(10).join(f"- {c}: {_fmt(p)} ({n} annonces)" for c,p,n in top_cities)}

REPERES DE PRIX AU SENEGAL:
- Villa Almadies: 150-500M FCFA | Loyer: 1-5M/mois
- Appartement Mermoz: 40-120M | Loyer: 200-800K/mois
- Studio Plateau: 10-35M | Loyer: 60-200K/mois
- Terrain Pikine: 3-25M FCFA
- Chambre (loyer): 30-150K/mois"""

    return ctx


# ── Appel Groq ───────────────────────────────────────────────────────────────

def _groq_response(question, context, history=None):
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return None

        client = Groq(api_key=api_key)

        system_prompt = f"""Tu es ImmoAI, un assistant intelligent et polyvalent sur la plateforme ImmoPredict SN.

TU REPONDS A TOUTES LES QUESTIONS sans exception : immobilier, culture generale, mathematiques, 
histoire, geographie, sciences, actualites, conseils pratiques, programmation, cuisine, sport, etc.

{context}

REGLES IMPORTANTES:
1. Reponds TOUJOURS en francais
2. Sois precis, structure et utile
3. Pour l'immobilier senegalais, utilise les donnees reelles ci-dessus
4. Pour les autres sujets, reponds avec tes connaissances generales
5. Formate les prix en FCFA (85M FCFA, 300K FCFA)
6. Utilise du HTML pour formater : <b>, <br>, <em>, <ul>, <li>
7. NE REFUSE JAMAIS de repondre - donne toujours une reponse utile
8. Si on te demande un calcul, fais-le
9. Si on te demande une comparaison, structure-la en tableau ou liste
10. Sois chaleureux et professionnel

EXEMPLES DE REPONSES ATTENDUES:
- "Quelle est la capitale du Senegal ?" -> Reponds: Dakar
- "Calcule 15% de 80M" -> Reponds: 12M FCFA
- "Que vaut une villa aux Almadies ?" -> Donne une fourchette basee sur les donnees
- "Qui est Sadio Mane ?" -> Reponds sur Sadio Mane
- "Comment faire un tieboudienne ?" -> Donne la recette
- "Quelle est la rentabilite d'un bien a 80M loue 500K/mois ?" -> Calcule: (500K*12)/80M = 7.5%"""

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-8:])
        messages.append({"role": "user", "content": question})

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.4,
        )
        return response.choices[0].message.content

    except ImportError:
        logger.warning("Module groq non installe. pip install groq")
        return None
    except Exception as e:
        logger.warning(f"Groq error: {e}")
        return None


# ── Analyses locales (fallback sans Groq) ────────────────────────────────────

def _analyze_prix_stats(crit):
    data = _get_db_data()
    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if crit.get("city"):
        city_q = crit["city"].lower()
        filtered = [d for d in filtered if str(d.get("city","")).lower().find(city_q[:5]) >= 0]
    if crit.get("type"):
        type_q = crit["type"].lower()
        filtered = [d for d in filtered if str(d.get("property_type","")).lower().find(type_q[:4]) >= 0]
    if not filtered:
        # Utiliser les prix de reference
        tkey = (crit.get("type","appartement").lower(), crit.get("transaction","vente"))
        ref = PRIX_REF.get(tkey)
        if ref:
            loc = f" a <b>{crit['city']}</b>" if crit.get('city') else ""
            mult = next((v for k,v in ZONE_MULT.items() if crit.get('city','').lower().startswith(k)), 1.0)
            return (f"Estimation pour un(e) <b>{crit.get('type','bien')}</b>{loc} :<br>"
                    f"- Bas de gamme : <b>{_fmt(ref[0]*mult)}</b><br>"
                    f"- Prix moyen : <b>{_fmt(ref[1]*mult)}</b><br>"
                    f"- Haut de gamme : <b>{_fmt(ref[2]*mult)}</b>"), []
        return "Pas assez de donnees pour ces criteres.", []

    prices = [d["price"] for d in filtered]
    scope = ""
    if crit.get('city'): scope += f" a <b>{crit['city']}</b>"
    if crit.get('type'): scope += f" pour les <b>{crit['type']}s</b>"

    lines = [f"<b>Analyse sur {len(prices)} annonces</b>{scope} :",
             f"- Minimum : <b>{_fmt(min(prices))}</b>",
             f"- Mediane : <b>{_fmt(stats.median(prices))}</b>",
             f"- Moyenne : <b>{_fmt(stats.mean(prices))}</b>",
             f"- Maximum : <b>{_fmt(max(prices))}</b>"]

    props = _make_props(
        sorted([{"title":d.get("title",""),"price":d["price"],"city":d.get("city",""),
                 "property_type":d.get("property_type","")} for d in filtered],
               key=lambda x: abs(x["price"]-stats.median(prices)))[:5]
    )
    return "<br>".join(lines), props


def _analyze_comparaison(crit):
    data = _get_db_data()
    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if crit.get("type"):
        type_q = crit["type"].lower()
        filtered = [d for d in filtered if str(d.get("property_type","")).lower().find(type_q[:4]) >= 0]

    by_city = defaultdict(list)
    for d in filtered:
        c = str(d.get("city","") or "").strip().title()
        if c and c != "Inconnu": by_city[c].append(d["price"])

    top = sorted([(c,ps) for c,ps in by_city.items() if len(ps)>=3],
                 key=lambda x: stats.median(x[1]))

    if not top:
        return "Pas assez de donnees pour comparer.", []

    cheapest = top[:4]
    expensive = top[-4:][::-1]

    lines = ["<b>Quartiers les plus abordables :</b>"]
    for c, ps in cheapest:
        lines.append(f"- {c} : <b>{_fmt(stats.median(ps))}</b> ({len(ps)} ann.)")
    lines.append("<br><b>Quartiers les plus chers :</b>")
    for c, ps in expensive:
        lines.append(f"- {c} : <b>{_fmt(stats.median(ps))}</b> ({len(ps)} ann.)")

    return "<br>".join(lines), []


def _analyze_stats_marche():
    data = _get_db_data()
    prices = [d["price"] for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if not prices:
        return "Donnees en cours de chargement.", []

    types = Counter(str(d.get("property_type","") or "").strip() for d in data if d.get("price"))
    lines = [f"<b>Marche immobilier — ImmoPredict SN</b> ({len(data):,} annonces) :",
             f"- Prix median : <b>{_fmt(stats.median(prices))}</b>",
             f"- Prix moyen : <b>{_fmt(stats.mean(prices))}</b>",
             f"- De <b>{_fmt(min(prices))}</b> a <b>{_fmt(max(prices))}</b>",
             "", "<b>Repartition par type :</b>"]
    for t, n in types.most_common(6):
        lines.append(f"- {t or 'Autre'} : <b>{n:,}</b> annonces")
    return "<br>".join(lines), []


def _analyze_budget(crit, question):
    mn = crit.get("min_price") or crit.get("max_price")
    mx = crit.get("max_price") or (mn * 1.4 if mn else None)
    if not mx:
        nums = _extract_numbers(question)
        for n in nums:
            if n >= 1_000_000: mx = n; mn = n * 0.7; break
            elif n >= 1: mx = n * 1_000_000; mn = mx * 0.7; break
    if not mx:
        return "Precisez votre budget.<br><em>Ex: Avec 100M FCFA, que puis-je acheter ?</em>", []

    data = _get_db_data()
    budget_f = [d for d in data if d.get("price") and PRICE_MIN <= d["price"] <= mx * 1.1]
    if crit.get("city"):
        city_q = crit["city"].lower()
        budget_f = [d for d in budget_f if str(d.get("city","")).lower().find(city_q[:5]) >= 0]

    if not budget_f:
        return f"Avec <b>{_fmt(mx)}</b>, aucune annonce trouvee. Essayez un budget plus eleve.", []

    types = Counter(str(d.get("property_type","") or "").strip() for d in budget_f)
    loc = f" a {crit['city']}" if crit.get("city") else " au Senegal"
    lines = [f"Avec <b>{_fmt(mx)}</b>{loc} :"]
    for t, n in types.most_common(5):
        ps = [d["price"] for d in budget_f if str(d.get("property_type","")).strip() == t]
        if ps: lines.append(f"- <b>{n} {t}{'s' if n>1 else ''}</b> — de {_fmt(min(ps))} a {_fmt(max(ps))}")

    props = _make_props(sorted(budget_f, key=lambda x: x.get("price",0), reverse=True)[:5])
    return "<br>".join(lines), props


def _analyze_recommandation(question):
    is_loc = any(k in question.lower() for k in KW_LOC)
    data = _get_db_data()
    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    by_city = defaultdict(list)
    for d in filtered:
        c = str(d.get("city","") or "").strip().title()
        if c and c != "Inconnu": by_city[c].append(d["price"])
    if not by_city:
        return "Pas assez de donnees.", []

    all_meds = [stats.median(ps) for ps in by_city.values() if len(ps) >= 3]
    if not all_meds:
        return "Pas assez de donnees.", []
    g_med = stats.median(all_meds)

    scored = [(c, stats.median(ps), len(ps),
               len(ps)*0.4 + (1/(stats.median(ps)/g_med+.001))*0.6)
              for c, ps in by_city.items() if len(ps) >= 3]
    scored.sort(key=lambda x: x[3], reverse=True)

    action = "louer" if is_loc else "investir"
    lines = [f"<b>Meilleures zones pour {action}</b> :"]
    for c, med, n, _ in scored[:6]:
        lines.append(f"- <b>{c}</b> : {_fmt(med)} median ({n} annonces)")

    lines.append(f"<br><em>Conseil : {scored[0][0]} offre le meilleur rapport offre/prix.</em>")
    return "<br>".join(lines), []


def _analyze_recents():
    data = _get_db_data()
    if not data:
        return "Aucune donnee disponible.", []
    recent = data[:8]
    lines = ["<b>Biens recents sur ImmoPredict SN :</b>"]
    for d in recent:
        city = str(d.get("city","") or "").strip().title()
        ptype = str(d.get("property_type","") or "")
        price = d.get("price", 0)
        lines.append(f"- <b>{_fmt(price)}</b> — {ptype} a {city}")
    return "<br>".join(lines), _make_props(recent)


def _calcul_rentabilite(question):
    nums = _extract_numbers(question)
    prix_achat = loyer = None

    # Essayer d'extraire prix d'achat et loyer
    tl = _normalize(question)
    m_prix = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|million)", tl)
    m_loyer = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:k|mille|000)?\s*(?:/\s*mois|mensuel|loyer|loue)", tl)

    if m_prix:
        v = float(m_prix.group(1).replace(",","."))
        prix_achat = v * 1_000_000 if v < 10_000 else v
    if m_loyer:
        v = float(m_loyer.group(1).replace(",","."))
        loyer = v * 1_000 if v < 10_000 else v

    if not prix_achat and len(nums) >= 1:
        prix_achat = nums[0] * 1_000_000 if nums[0] < 10_000 else nums[0]
    if not loyer and len(nums) >= 2:
        loyer = nums[1] * 1_000 if nums[1] < 10_000 else nums[1]

    if not prix_achat or not loyer:
        return ("Pour calculer la rentabilite, j'ai besoin de :<br>"
                "- <b>Prix d'achat</b> du bien<br>"
                "- <b>Loyer mensuel</b><br><br>"
                "<em>Exemple : Rentabilite d'un bien a 80M loue 500K/mois</em>"), []

    loyer_annuel = loyer * 12
    rentabilite_brute = (loyer_annuel / prix_achat) * 100
    # Estimation charges (environ 20%)
    rentabilite_nette = rentabilite_brute * 0.80
    retour_investissement = prix_achat / loyer_annuel

    lines = [
        f"<b>Calcul de rentabilite</b>",
        f"- Prix d'achat : <b>{_fmt(prix_achat)}</b>",
        f"- Loyer mensuel : <b>{_fmt(loyer)}</b>",
        f"- Loyer annuel : <b>{_fmt(loyer_annuel)}</b>",
        "",
        f"<b>Rentabilite brute : {rentabilite_brute:.1f}%</b>",
        f"Rentabilite nette (apres charges ~20%) : <b>{rentabilite_nette:.1f}%</b>",
        f"Retour sur investissement : <b>{retour_investissement:.1f} ans</b>",
        "",
    ]
    if rentabilite_brute >= 8:
        lines.append("<em>Excellent rendement ! Au-dessus de la moyenne du marche.</em>")
    elif rentabilite_brute >= 5:
        lines.append("<em>Bon rendement, dans la moyenne du marche senegalais.</em>")
    else:
        lines.append("<em>Rendement modeste. Envisagez de negocier le prix d'achat.</em>")

    return "<br>".join(lines), []


def _calcul_mensualite(question):
    nums = _extract_numbers(question)
    montant = taux = duree = None

    tl = _normalize(question)
    m_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m|million)", tl)
    m_t = re.search(r"(\d+(?:[.,]\d+)?)\s*%", tl)
    m_d = re.search(r"(\d+)\s*(?:an|annee|ans)", tl)

    if m_m: montant = float(m_m.group(1).replace(",",".")) * 1_000_000
    if m_t: taux = float(m_t.group(1).replace(",","."))
    if m_d: duree = int(m_d.group(1))

    if not montant:
        montant = nums[0] * 1_000_000 if nums and nums[0] < 100_000 else (nums[0] if nums else None)
    if not taux: taux = 8.0  # Taux moyen Senegal
    if not duree: duree = 20  # 20 ans par defaut

    if not montant:
        return ("Pour calculer les mensualites, precisez :<br>"
                "- <b>Montant</b> de l'emprunt<br>"
                "- <b>Taux</b> (defaut: 8%)<br>"
                "- <b>Duree</b> (defaut: 20 ans)<br><br>"
                "<em>Exemple : Mensualite pour un pret de 50M sur 20 ans a 8%</em>"), []

    # Calcul mensualite (formule amortissement)
    r = taux / 100 / 12
    n = duree * 12
    if r > 0:
        mensualite = montant * (r * (1+r)**n) / ((1+r)**n - 1)
    else:
        mensualite = montant / n

    cout_total = mensualite * n
    cout_interet = cout_total - montant

    lines = [
        f"<b>Simulation de credit immobilier</b>",
        f"- Montant emprunte : <b>{_fmt(montant)}</b>",
        f"- Taux annuel : <b>{taux}%</b>",
        f"- Duree : <b>{duree} ans</b> ({n} mois)",
        "",
        f"<b>Mensualite : {_fmt(mensualite)}/mois</b>",
        f"Cout total du credit : <b>{_fmt(cout_total)}</b>",
        f"Total des interets : <b>{_fmt(cout_interet)}</b>",
    ]
    return "<br>".join(lines), []


def _info_frais_notaire(question):
    nums = _extract_numbers(question)
    prix = None
    if nums:
        prix = nums[0] * 1_000_000 if nums[0] < 100_000 else nums[0]

    lines = [
        "<b>Frais lies a l'achat immobilier au Senegal :</b>",
        "",
        "- <b>Frais de notaire</b> : 6-8% du prix de vente",
        "- <b>Droits d'enregistrement</b> : 5% du prix",
        "- <b>Frais de conservation fonciere</b> : 1%",
        "- <b>Honoraires du notaire</b> : 1-2%",
        "- <b>TVA</b> : 18% (sur le neuf uniquement)",
    ]
    if prix:
        frais_min = prix * 0.06
        frais_max = prix * 0.08
        lines.append(f"<br>Pour un bien a <b>{_fmt(prix)}</b> :")
        lines.append(f"Frais estimes : <b>{_fmt(frais_min)}</b> a <b>{_fmt(frais_max)}</b>")
        lines.append(f"Budget total : <b>{_fmt(prix + frais_min)}</b> a <b>{_fmt(prix + frais_max)}</b>")

    return "<br>".join(lines), []


def _info_demarches():
    return ("<b>Etapes pour acheter un bien au Senegal :</b><br><br>"
            "<b>1.</b> Definir votre budget et vos criteres<br>"
            "<b>2.</b> Rechercher le bien (ImmoPredict SN vous aide !)<br>"
            "<b>3.</b> Visiter le bien et verifier le titre foncier<br>"
            "<b>4.</b> Negocier le prix avec le vendeur<br>"
            "<b>5.</b> Signer un avant-contrat (compromis de vente)<br>"
            "<b>6.</b> Obtenir le financement (credit bancaire si necessaire)<br>"
            "<b>7.</b> Passage chez le notaire pour l'acte authentique<br>"
            "<b>8.</b> Paiement et transfert de propriete<br>"
            "<b>9.</b> Enregistrement au cadastre<br><br>"
            "<em>Delai moyen : 2-4 mois. Documents requis : CNI, justificatif de revenus, titre foncier.</em>"), []


def _info_quartier(question):
    tl = _normalize(question)
    city = next((c.title() for c in sorted(CITIES_SN, key=len, reverse=True) if c in tl), None)

    quartiers_info = {
        "Almadies": "Zone huppee de Dakar. Ambassades, restaurants haut de gamme, plages. Tres securise mais cher.",
        "Ngor": "Proche Almadies, vue sur l'ile de Ngor. Calme, residentiel, plage. Prix eleves.",
        "Mermoz": "Quartier residentiel moyen-haut. Proximite VDN, commerces, ecoles. Bon compromis.",
        "Ouakam": "Village traditionnel lebou integre a Dakar. Mixte, bon acces plage. Prix moyens.",
        "Plateau": "Centre-ville historique. Bureaux, ministeres, banques. Bruyant mais tres connecte.",
        "Fann": "Proche universite, residentiel calme. Hopital Fann. Bon pour familles.",
        "Yoff": "Ancien village de pecheurs. Aeroport a proximite. En developpement. Prix accessibles.",
        "Sacre Coeur": "Residentiel, securise, beaucoup d'expatries. Commerces, restaurants. Prix eleves.",
        "Pikine": "Banlieue populaire. Tres dense, moins cher. Transports en commun.",
        "Guediawaye": "Banlieue populaire au nord de Pikine. Prix bas. En expansion.",
        "Saly": "Station balneaire. Tourisme, expatries. Ideal pour location saisonniere.",
        "Thies": "2eme ville du Senegal. Moins cher que Dakar. En croissance.",
        "Mbour": "Ville cotiere, peche et tourisme. Prix abordables. Potentiel locatif.",
        "Vdn": "Voie de Degagement Nord. Zone d'affaires moderne. Bureaux et residences.",
    }

    if city:
        info = quartiers_info.get(city, f"Quartier de {city} au Senegal.")
        # Chercher les prix dans la DB
        data = _get_db_data()
        city_prices = [d["price"] for d in data
                       if d.get("price") and d["price"] >= PRICE_MIN
                       and str(d.get("city","")).lower().find(city.lower()[:5]) >= 0]
        prix_info = ""
        if city_prices:
            prix_info = (f"<br><br><b>Prix a {city} :</b><br>"
                        f"- Median : <b>{_fmt(stats.median(city_prices))}</b><br>"
                        f"- De {_fmt(min(city_prices))} a {_fmt(max(city_prices))}<br>"
                        f"- {len(city_prices)} annonces disponibles")
        return f"<b>{city}</b><br>{info}{prix_info}", []
    else:
        lines = ["<b>Quartiers populaires de Dakar :</b>", ""]
        for q, info in list(quartiers_info.items())[:8]:
            lines.append(f"- <b>{q}</b> : {info[:60]}...")
        return "<br>".join(lines), []


# ── Endpoint principal ────────────────────────────────────────────────────────

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect


@login_required(login_url='/immo/login/')
def api_chatbot(request):
    """Chatbot ImmoAI — Groq en priorite, fallback local intelligent."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST requis'}, status=405)
    try:
        import json as _json
        body = _json.loads(request.body)
        q    = body.get('message','').strip()
        hist = body.get('history', [])
        if not q:
            return JsonResponse({'error': 'Message vide'}, status=400)

        # ── Salutation ───────────────────────────────────────────
        if _is_greeting(q):
            return JsonResponse({
                'response': (
                    "Bonjour ! Je suis <b>ImmoAI</b>, votre assistant intelligent.<br><br>"
                    "Je reponds a <b>toutes vos questions</b> :<br>"
                    "- Immobilier : prix, quartiers, estimations<br>"
                    "- Calculs : rentabilite, mensualites, frais<br>"
                    "- Conseils : ou investir, demarches, fiscalite<br>"
                    "- Culture generale, et bien plus !<br><br>"
                    "<em>Essayez : Que vaut une villa aux Almadies ?</em>"
                ),
                'total': 0, 'properties': []
            })

        # ── Essayer Groq d'abord ─────────────────────────────────
        context = _build_context()
        groq_resp = _groq_response(q, context, hist)

        if groq_resp:
            # Aussi faire une recherche si c'est immobilier
            intent = _detect_intent(q)
            props = []
            total = 0
            if intent in ("prix_stats", "budget_conseil", "recents", "proximite"):
                crit = _parse(q)
                has_crit = any(crit.get(k) for k in ['city','type','min_price','max_price','bedrooms'])
                if has_crit:
                    results, total = _search(crit)
                    props = _make_props(results)
            return JsonResponse({'response': groq_resp, 'total': total,
                               'properties': props, 'source': 'groq'})

        # ── Fallback local intelligent ───────────────────────────
        intent = _detect_intent(q)
        crit   = _parse(q)

        if intent == "prix_stats":
            resp, props = _analyze_prix_stats(crit)
        elif intent == "comparaison":
            resp, props = _analyze_comparaison(crit)
        elif intent == "stats_marche":
            resp, props = _analyze_stats_marche()
        elif intent == "budget_conseil":
            resp, props = _analyze_budget(crit, q)
        elif intent == "recommandation":
            resp, props = _analyze_recommandation(q)
        elif intent == "recents":
            resp, props = _analyze_recents()
        elif intent == "calcul_rentabilite":
            resp, props = _calcul_rentabilite(q)
        elif intent == "calcul_mensualite":
            resp, props = _calcul_mensualite(q)
        elif intent == "frais_notaire":
            resp, props = _info_frais_notaire(q)
        elif intent == "demarches":
            resp, props = _info_demarches()
        elif intent == "info_quartier":
            resp, props = _info_quartier(q)
        else:
            # Recherche immobiliere si criteres detectes
            has_crit = any(crit.get(k) for k in ['city','type','transaction','min_price','max_price','bedrooms'])
            if has_crit:
                results, total = _search(crit)
                parts = []
                if crit.get('city'):        parts.append(f"<b>{crit['city']}</b>")
                if crit.get('type'):        parts.append(f"<b>{crit['type']}</b>")
                if crit.get('transaction'): parts.append(f"en <b>{crit['transaction']}</b>")
                mn, mx = crit.get('min_price'), crit.get('max_price')
                if mn and mx: parts.append(f"budget <b>{_fmt(mn)}-{_fmt(mx)}</b>")

                if total == 0:
                    resp = "Aucun bien trouve. Essayez des criteres plus larges."
                else:
                    prices_r = sorted([r["price"] for r in results if r.get("price") and r["price"] >= PRICE_MIN])
                    resp = f"<b>{total}</b> biens trouves."
                    if prices_r: resp += f" Prix : de <b>{_fmt(prices_r[0])}</b> a <b>{_fmt(prices_r[-1])}</b>."
                if parts: resp = f"Recherche : {', '.join(parts)}. " + resp
                props = _make_props(results)
            else:
                # Reponse locale generale - donner le resume du marche
                data = _get_db_data()
                if data:
                    prices = [d["price"] for d in data if d.get("price") and d["price"] >= PRICE_MIN]
                    if prices:
                        resp = (f"<b>ImmoPredict SN</b> — {len(data):,} annonces indexees<br>"
                                f"Prix median : <b>{_fmt(stats.median(prices))}</b><br><br>"
                                f"Je peux vous aider avec :<br>"
                                f"- <b>Prix</b> : <em>Que vaut un appartement a Mermoz ?</em><br>"
                                f"- <b>Budget</b> : <em>Avec 50M, que puis-je acheter ?</em><br>"
                                f"- <b>Quartiers</b> : <em>Quel quartier est le plus abordable ?</em><br>"
                                f"- <b>Rentabilite</b> : <em>Calcule la rentabilite d'un bien a 80M loue 500K/mois</em><br>"
                                f"- <b>Credit</b> : <em>Mensualite pour un pret de 50M sur 20 ans</em><br>"
                                f"- <b>Demarches</b> : <em>Comment acheter un bien au Senegal ?</em>")
                    else:
                        resp = "Base de donnees en cours de chargement. Reessayez dans un instant."
                else:
                    resp = "Base de donnees en cours de chargement. Reessayez dans un instant."
                props = []

        return JsonResponse({'response': resp, 'total': len(props),
                           'properties': props, 'source': 'local'})

    except Exception as e:
        logger.error(f"Chatbot: {e}")
        return JsonResponse({'response': "Une erreur s'est produite. Reessayez.",
                           'total': 0, 'properties': []})
