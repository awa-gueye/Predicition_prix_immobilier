"""
ImmoPredict SN — chatbot_groq.py
Chatbot ImmoAI propulsé par Groq (llama-3.3-70b-versatile).
Fallback vers analyse statistique locale si Groq indisponible.
"""
import re, json, logging, os
import statistics as stats

logger = logging.getLogger(__name__)

PRICE_MIN   = 500_000
PRICE_MAX   = 5_000_000_000
GROQ_MODEL  = "llama-3.3-70b-versatile"

CITIES_SN = [
    "almadies","ngor","ouakam","mermoz","pikine","guediawaye","plateau","fann",
    "yoff","rufisque","liberte","hlm","sicap","grand yoff","keur massar",
    "medina","thies","mbour","dakar","parcelles","sacre coeur","vdn","saly",
    "patte d oie","dieuppeul","fass","colobane","hann","diamniadio","bargny",
]
TYPE_MAP = {
    "villa":       ["villa"],
    "appartement": ["appart","f2","f3","f4","f5"],
    "terrain":     ["terrain","parcelle"],
    "duplex":      ["duplex"],
    "studio":      ["studio","f1"],
    "maison":      ["maison"],
    "local":       ["local","commerce","bureau"],
    "chambre":     ["chambre"],
}
KW_LOC = ["louer","location","locat","bail","mensuel","loyer","a louer"]
KW_VTE = ["vendre","acheter","achat","vente","a vendre"]
GREETINGS = {"bonjour","bonsoir","salut","hello","hi","coucou","bonne nuit",
             "merci","ok","oui","non","svp","stp"}

ANALYTIC_PATTERNS = [
    (r"(?:prix|valeur|cout|combien|que vaut|quel est le prix).{0,40}(?:moyen|median|typique)", "prix_stats"),
    (r"(?:que vaut|combien coute|quel prix).{0,50}(?:chambre|studio|villa|appart|terrain)", "prix_stats"),
    (r"(?:difference|comparer|plus cher|moins cher|meilleur marche)", "comparaison"),
    (r"(?:quel).{0,20}(?:quartier|ville).{0,20}(?:cher|abordable|moins cher)", "comparaison"),
    (r"(?:statistique|tendance|marche immobilier|etat du marche|apercu|situation)", "stats_marche"),
    (r"(?:avec|pour|quel bien|que puis.je|que peut.on).{0,30}(?:budget|million|fcfa)", "budget_conseil"),
    (r"(?:recommander|conseil|meilleur|ideal).{0,50}(?:investir|acheter|louer|quartier)", "recommandation"),
    (r"(?:ou investir|ou acheter|ou louer|ou habiter)", "recommandation"),
]


def _is_greeting(text):
    tl = text.lower().strip().rstrip("!?.,")
    return tl in GREETINGS or len(tl.replace(" ","")) < 4


def _detect_intent(text):
    tl = (text.lower()
          .replace("é","e").replace("è","e").replace("à","a")
          .replace("ê","e").replace("â","a").replace("ç","c"))
    for pattern, intent in ANALYTIC_PATTERNS:
        if re.search(pattern, tl):
            return intent
    return "recherche"


def _fmt(p):
    if not p or float(p) < 100: return "—"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


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
    import re
    tl = (text.lower()
          .replace("é","e").replace("è","e").replace("à","a")
          .replace("ê","e").replace("â","a").replace("ç","c")
          .replace("\u2019","'"))
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
                m5 = re.search(r"([\d]{4,})\s*(?:fcfa|cfa)?", tl)
                if m5:
                    v = _amt(m5.group(1))
                    if v: mn = v*0.7; mx = v*1.4

    if mn and mn <= 0: mn = None
    if mx and mx <= 0: mx = None

    city  = next((c.title() for c in sorted(CITIES_SN, key=len, reverse=True) if c in tl), None)
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

    return {"city":city, "type":ptype, "transaction":txn,
            "min_price":mn, "max_price":mx, "bedrooms":beds}


def _get_db_data():
    """Charge les données de la DB."""
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        MODELS = [CoinAfriqueProperty, ExpatDakarProperty,
                  LogerDakarProperty, DakarVenteProperty]
        results = []
        for model in MODELS:
            for p in model.objects.filter(
                price__gte=PRICE_MIN, price__lte=PRICE_MAX
            ).values("price","city","property_type","surface_area","bedrooms","statut","title")[:2000]:
                results.append(p)
        return results
    except Exception as e:
        logger.warning(f"DB: {e}")
        return []


def _search(crit):
    """Recherche dans toutes les tables."""
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        MODELS = [(CoinAfriqueProperty,"coinafrique"),(ExpatDakarProperty,"expat_dakar"),
                  (LogerDakarProperty,"loger_dakar"),(DakarVenteProperty,"dakarvente"),
                  ]
        results = []
        for model, src in MODELS:
            qs = model.objects.filter(price__gte=PRICE_MIN, price__lte=PRICE_MAX)
            if crit.get("city"):      qs = qs.filter(city__icontains=crit["city"])
            if crit.get("type"):      qs = qs.filter(property_type__icontains=crit["type"])
            if crit.get("min_price"): qs = qs.filter(price__gte=crit["min_price"])
            if crit.get("max_price"): qs = qs.filter(price__lte=crit["max_price"])
            if crit.get("bedrooms"):  qs = qs.filter(bedrooms__gte=crit["bedrooms"])
            for p in qs.order_by("price").values(
                "id","title","price","city","property_type","surface_area","bedrooms","url")[:80]:
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


def _build_context():
    """Construit le contexte marché pour Groq."""
    data = _get_db_data()
    if not data:
        return "Aucune donnée disponible."

    prices = [float(d["price"]) for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if not prices:
        return "Données de prix insuffisantes."

    from collections import Counter
    types = Counter(str(d.get("property_type","") or "").strip() for d in data)
    cities_prices = {}
    for d in data:
        c = str(d.get("city","") or "").strip().title()
        if c and c != "Inconnu" and d.get("price"):
            cities_prices.setdefault(c, []).append(float(d["price"]))

    top_cities = sorted(
        [(c, stats.median(ps), len(ps)) for c, ps in cities_prices.items() if len(ps) >= 5],
        key=lambda x: x[1], reverse=True
    )[:8]

    ctx = f"""DONNÉES DU MARCHÉ IMMOBILIER SÉNÉGALAIS (données réelles):
- Total annonces: {len(data):,}
- Prix médian global: {_fmt(stats.median(prices))}
- Prix moyen global: {_fmt(stats.mean(prices))}
- Prix minimum: {_fmt(min(prices))}
- Prix maximum: {_fmt(max(prices))}

TOP TYPES DE BIENS:
{chr(10).join(f"- {t}: {n} annonces" for t,n in types.most_common(6))}

PRIX MÉDIANS PAR QUARTIER (top 8):
{chr(10).join(f"- {c}: {_fmt(p)} ({n} ann.)" for c,p,n in top_cities)}"""

    return ctx


def _groq_response(question, context, history=None):
    """Appel à l'API Groq."""
    try:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return None

        client = Groq(api_key=api_key)

        system_prompt = f"""Tu es ImmoAI, l'assistant immobilier intelligent de la plateforme ImmoPredict SN.
Tu aides les utilisateurs à analyser le marché immobilier sénégalais.

{context}

RÈGLES:
- Réponds en français, de façon concise et professionnelle
- Utilise les données réelles fournies ci-dessus
- Formate les prix en FCFA (ex: 85M FCFA, 300K FCFA)
- Si tu cites des prix, base-toi sur les données réelles du marché
- Pour les questions hors immobilier, recentre sur le marché immobilier sénégalais
- Sois direct et utile, pas trop long (max 3-4 phrases sauf si nécessaire)
- Tu peux utiliser du HTML minimal (<b>, <br>) pour formater ta réponse"""

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-6:])  # Garder les 3 derniers échanges
        messages.append({"role": "user", "content": question})

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.4,
        )
        return response.choices[0].message.content

    except ImportError:
        logger.warning("groq non installé. pip install groq")
        return None
    except Exception as e:
        logger.warning(f"Groq error: {e}")
        return None


# ── Analyses locales de fallback ──────────────────────────────────────────────

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
        return "Aucune donnée disponible pour ces critères.", []
    prices = [d["price"] for d in filtered]
    scope = f"{'à <b>' + crit['city'] + '</b> ' if crit.get('city') else ''}{'pour les <b>' + crit['type'] + 's</b>' if crit.get('type') else ''}"
    lines = [f"Analyse sur <b>{len(prices)}</b> annonces {scope} :",
             f"• Minimum : <b>{_fmt(min(prices))}</b>",
             f"• Médiane : <b>{_fmt(stats.median(prices))}</b>",
             f"• Moyenne : <b>{_fmt(stats.mean(prices))}</b>",
             f"• Maximum : <b>{_fmt(max(prices))}</b>"]
    props = [{"title":str(d.get("title","") or "")[:55],"price":d["price"],
              "price_fmt":_fmt(d["price"]),"city":str(d.get("city","") or ""),
              "type":str(d.get("property_type","") or ""),"source":"","surface":d.get("surface_area",""),
              "bedrooms":d.get("bedrooms","")} for d in sorted(filtered, key=lambda x: abs(x["price"]-stats.median(prices)))[:5]]
    return "<br>".join(lines), props


def _analyze_comparaison(crit):
    from collections import defaultdict
    data = _get_db_data()
    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if crit.get("type"):
        type_q = crit["type"].lower()
        filtered = [d for d in filtered if str(d.get("property_type","")).lower().find(type_q[:4]) >= 0]
    by_city = defaultdict(list)
    for d in filtered:
        c = str(d.get("city","") or "").strip().title()
        if c and c != "Inconnu": by_city[c].append(d["price"])
    top = sorted([(c,ps) for c,ps in by_city.items() if len(ps)>=5],
                 key=lambda x: stats.median(x[1]), reverse=True)[:8]
    if not top: return "Pas assez de données.", []
    lines = ["Comparaison prix médians par quartier :"]
    for c, ps in top:
        lines.append(f"• <b>{c}</b> : {_fmt(stats.median(ps))} ({len(ps)} ann.)")
    lines.append(f"<br><b>{top[0][0]}</b> est le plus cher, <b>{top[-1][0]}</b> le plus abordable.")
    return "<br>".join(lines), []


def _analyze_stats_marche():
    data = _get_db_data()
    prices = [d["price"] for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    if not prices: return "Données insuffisantes.", []
    from collections import Counter
    types = Counter(str(d.get("property_type","") or "").strip() for d in data if d.get("price") and d["price"] >= PRICE_MIN)
    lines = [f"<b>Marché immobilier — ImmoPredict SN</b> ({len(data):,} annonces) :",
             f"• Prix médian : <b>{_fmt(stats.median(prices))}</b>",
             f"• Prix moyen  : <b>{_fmt(stats.mean(prices))}</b>",
             f"• De <b>{_fmt(min(prices))}</b> à <b>{_fmt(max(prices))}</b>",
             "", "<b>Répartition :</b>"]
    for t, n in types.most_common(5):
        lines.append(f"• {t or 'Autre'} : <b>{n:,}</b> annonces")
    return "<br>".join(lines), []


def _analyze_budget(crit, question):
    mn = crit.get("min_price") or crit.get("max_price")
    mx = crit.get("max_price") or (mn * 1.4 if mn else None)
    if not mx:
        m = re.search(r"([\d][\d\s]{1,12}[\d])\s*(?:fcfa|cfa)?", question.lower())
        if m:
            v = _amt(m.group(1).replace(" ",""))
            if v and v >= PRICE_MIN: mx = v; mn = v * 0.7
    if not mx:
        return ("Précisez votre budget.<br>"
                "<small>Ex : <em>Avec 100M FCFA que puis-je acheter ?</em></small>"), []
    data = _get_db_data()
    filtered = [d for d in data if d.get("price") and PRICE_MIN <= d["price"] <= mx * 1.1]
    if crit.get("city"):
        city_q = crit["city"].lower()
        filtered = [d for d in filtered if str(d.get("city","")).lower().find(city_q[:5]) >= 0]
    budget_f = [d for d in filtered if d.get("price") and d["price"] <= mx]
    if not budget_f:
        return f"Avec {_fmt(mx)}, aucune annonce correspondante. Essayez un budget plus élevé.", []
    from collections import Counter
    types = Counter(str(d.get("property_type","") or "").strip() for d in budget_f)
    loc = f"à {crit['city']}" if crit.get("city") else "au Sénégal"
    lines = [f"Avec <b>{_fmt(mx)}</b> {loc} :"]
    for t, n in types.most_common(5):
        ps = [d["price"] for d in budget_f if str(d.get("property_type","")).strip() == t]
        if ps: lines.append(f"• <b>{n} {t}{'s' if n>1 else ''}</b> — de {_fmt(min(ps))} à {_fmt(max(ps))}")
    props = [{"title":str(d.get("title","") or "")[:55],"price":d["price"],
              "price_fmt":_fmt(d["price"]),"city":str(d.get("city","") or ""),
              "type":str(d.get("property_type","") or ""),"source":"",
              "surface":d.get("surface_area",""),"bedrooms":d.get("bedrooms","")}
             for d in sorted(budget_f, key=lambda x: x.get("price",0), reverse=True)[:5]]
    return "<br>".join(lines), props


def _analyze_recommandation(question):
    from collections import defaultdict
    is_loc = any(k in question.lower() for k in KW_LOC)
    is_vte = any(k in question.lower() for k in KW_VTE)
    data = _get_db_data()
    filtered = [d for d in data if d.get("price") and d["price"] >= PRICE_MIN]
    by_city = defaultdict(list)
    for d in filtered:
        c = str(d.get("city","") or "").strip().title()
        if c and c != "Inconnu": by_city[c].append(d["price"])
    if not by_city: return "Pas assez de données.", []
    all_meds = [stats.median(ps) for ps in by_city.values() if len(ps) >= 3]
    g_med = stats.median(all_meds) if all_meds else 1
    scored = [(c, stats.median(ps), len(ps), len(ps)*0.4 + (1/(stats.median(ps)/g_med+.001))*0.6)
              for c, ps in by_city.items() if len(ps) >= 3]
    scored.sort(key=lambda x: x[3], reverse=True)
    action = "louer" if is_loc else ("acheter" if is_vte else "investir")
    lines = [f"<b>Meilleures zones pour {action}</b> :"]
    for c, med, n, _ in scored[:5]:
        lines.append(f"• <b>{c}</b> : {_fmt(med)} ({n} ann.)")
    return "<br>".join(lines), []



def _answer_recent():
    """Retourne les biens les plus recents."""
    data = _get_db_data()
    if not data: return "Pas de donnees disponibles.", []
    recent = data[:10]  # First entries are typically most recent
    lines = ["<b>Biens recents sur ImmoPredict SN</b> :"]
    props = []
    for d in recent[:6]:
        city = str(d.get("city","") or "").strip().title()
        ptype = str(d.get("property_type","") or "")
        price = d.get("price", 0)
        lines.append(f"- <b>{_fmt(price)}</b> - {ptype} a {city}")
        props.append({"title":str(d.get("title",""))[:45],"price":price,"price_fmt":_fmt(price),"city":city,"type":ptype,"source":"","surface":"","bedrooms":""})
    return "<br>".join(lines), props


# ── Endpoint principal ────────────────────────────────────────────────────────

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect


@login_required(login_url='/immo/login/')
def api_chatbot(request):
    """Chatbot ImmoAI — Groq en priorité, fallback local."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST requis'}, status=405)
    try:
        import json as _json
        body = _json.loads(request.body)
        q    = body.get('message','').strip()
        hist = body.get('history', [])
        if not q:
            return JsonResponse({'error': 'Message vide'}, status=400)

        # ── Salutation ───────────────────────────────────────────────────────
        if _is_greeting(q):
            return JsonResponse({
                'response': (
                    "Bonjour ! Je suis <b>ImmoAI</b>, votre assistant immobilier intelligent.<br>"
                    "Je peux analyser les prix du marché, comparer les quartiers, "
                    "vous conseiller sur votre budget ou trouver des biens disponibles.<br>"
                    "<small style='opacity:.65'>Propulsé par Groq · ImmoPredict SN</small>"
                ),
                'total': 0, 'properties': []
            })

        # ── Essayer Groq ─────────────────────────────────────────────────────
        context = _build_context()
        groq_resp = _groq_response(q, context, hist)

        if groq_resp:
            # Aussi faire une recherche si c'est une requête de biens
            intent = _detect_intent(q)
            props  = []
            total  = 0
            if intent in ("recherche", "budget_conseil", "prix_stats"):
                crit = _parse(q)
                has_crit = any(crit.get(k) for k in ['city','type','min_price','max_price','bedrooms'])
                if has_crit:
                    results, total = _search(crit)
                    props = [{"title":str(p.get("title","") or "")[:55],
                              "price":p.get("price",0),
                              "price_fmt":_fmt(p.get("price",0)),
                              "city":str(p.get("city","") or ""),
                              "type":str(p.get("property_type","") or ""),
                              "source":p.get("source",""),
                              "surface":p.get("surface_area",""),
                              "bedrooms":p.get("bedrooms","")} for p in results[:6]]
            return JsonResponse({'response': groq_resp, 'total': total, 'properties': props, 'source': 'groq'})

        # ── Fallback local ───────────────────────────────────────────────────
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
        else:
            # Recherche classique
            has_crit = any(crit.get(k) for k in ['city','type','transaction','min_price','max_price','bedrooms'])
            if not has_crit:
                # Try Groq for general questions
                # Repondre localement sans Groq
                ql = q.lower()
                if any(w in ql for w in ["recent","nouveau","dernier"]):
                    resp, props = _answer_recent()
                elif any(w in ql for w in ["cher","abordable","moins cher","pas cher"]):
                    resp, props = _analyze_comparaison({})
                elif any(w in ql for w in ["statistique","stat","marche","apercu","resume"]):
                    resp, props = _analyze_stats_marche()
                elif any(w in ql for w in ["quartier","ville","zone","investir","recommand"]):
                    resp, props = _analyze_recommandation(q)
                else:
                    data = _get_db_data()
                    total_d = len(data)
                    if total_d > 0:
                        prices = [d["price"] for d in data if d.get("price") and d["price"] >= PRICE_MIN]
                        if prices:
                            resp = (f"<b>Marche ImmoPredict SN</b> ({total_d:,} annonces)<br>"
                                    f"Prix median : <b>{_fmt(stats.median(prices))}</b><br>"
                                    f"De <b>{_fmt(min(prices))}</b> a <b>{_fmt(max(prices))}</b><br><br>"
                                    f"Precisez votre question : quartier, type de bien, budget, etc.")
                        else:
                            resp = "Donnees en cours de chargement."
                    else:
                        resp = "Donnees en cours de chargement."
                    props = []
            else:
                results, total = _search(crit)
                parts = []
                if crit.get('city'):        parts.append(f"<b>{crit['city']}</b>")
                if crit.get('type'):        parts.append(f"<b>{crit['type']}</b>")
                if crit.get('transaction'): parts.append(f"en <b>{crit['transaction']}</b>")
                mn, mx = crit.get('min_price'), crit.get('max_price')
                if mn and mx:   parts.append(f"budget <b>{_fmt(mn)}–{_fmt(mx)}</b>")
                elif mx:        parts.append(f"max <b>{_fmt(mx)}</b>")
                if total == 0:
                    resp = "Aucun bien trouvé. Essayez des critères plus larges."
                elif total == 1:
                    resp = f"1 bien trouvé."
                else:
                    prices_r = sorted([r["price"] for r in results if r.get("price") and r["price"] >= PRICE_MIN])
                    resp = f"<b>{total}</b> biens trouvés."
                    if prices_r: resp += f" Prix : de <b>{_fmt(prices_r[0])}</b> à <b>{_fmt(prices_r[-1])}</b>."
                if parts: resp = f"Recherche : {', '.join(parts)}. " + resp
                props = [{"title":str(p.get("title","") or "")[:55],"price":p.get("price",0),
                          "price_fmt":_fmt(p.get("price",0)),"city":str(p.get("city","") or ""),
                          "type":str(p.get("property_type","") or ""),"source":p.get("source",""),
                          "surface":p.get("surface_area",""),"bedrooms":p.get("bedrooms","")}
                         for p in results[:6] if p.get("price",0) >= PRICE_MIN]

        return JsonResponse({'response': resp, 'total': len(props), 'properties': props, 'source': 'local'})

    except Exception as e:
        logger.error(f"Chatbot: {e}")
        return JsonResponse({'response': "Une erreur s'est produite. Réessayez.", 'total':0, 'properties':[]})
