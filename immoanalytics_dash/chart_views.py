"""
ImmoPredict SN — chart_views.py
Dashboard avec donnees reelles. Les donnees sont passees comme listes/dicts simples.
Les graphiques Plotly sont construits cote client en JavaScript.
"""
import json, logging
import statistics as _stats
from collections import Counter, defaultdict
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse as _JsonResponse

logger = logging.getLogger(__name__)

PRICE_MIN = 10_000
PRICE_MAX = 2_000_000_000

SRC_COLORS = {
    "coinafrique": "#F59E0B",
    "expat_dakar": "#2563EB",
    "loger_dakar": "#1B7A50",
    "dakarvente":  "#C0392B",
}
KW_LOC = ["louer","location","locat","bail","mensuel","loyer"]
KW_VTE = ["vendre","vente","achat","cession"]


def _txn(row):
    pt = str(row.get("property_type") or "").lower()
    if any(k in pt for k in ["louer","location","locat"]): return "Location"
    t = str(row.get("statut") or row.get("transaction") or "").lower()
    if any(k in t for k in KW_VTE): return "Vente"
    if any(k in t for k in KW_LOC): return "Location"
    txt = str(row.get("title") or "").lower()
    if any(k in txt for k in KW_LOC): return "Location"
    if any(k in txt for k in KW_VTE): return "Vente"
    price = row.get("price", 0) or 0
    if 10_000 <= price <= 2_000_000: return "Location"
    return "Vente"


VALID_TYPES = {
    "villa":"Villa","appartement":"Appartement","terrain":"Terrain",
    "duplex":"Duplex","studio":"Studio","maison":"Maison",
    "bureau":"Bureau","local":"Bureau","chambre":"Chambre","immeuble":"Immeuble",
}

def _clean_type(val):
    if not val: return "Autre"
    v = str(val).lower().strip()
    if "senegal" in v or "dakar" in v or len(v) > 35: return "Autre"
    for key, label in VALID_TYPES.items():
        if key in v: return label
    return "Autre"


def _load_data(max_per_source=5000):
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        SRCS = [
            (CoinAfriqueProperty, "coinafrique"),
            (ExpatDakarProperty,  "expat_dakar"),
            (LogerDakarProperty,  "loger_dakar"),
            (DakarVenteProperty,  "dakarvente"),
        ]
        BASE = ["id","price","surface_area","bedrooms","bathrooms","city","property_type","statut","title"]
        rows = []
        for model, src in SRCS:
            try:
                avail = [f.name for f in model._meta.get_fields()]
                fields = [f for f in BASE if f in avail]
                for p in model.objects.filter(price__isnull=False, price__gt=0).values(*fields)[:max_per_source]:
                    price = p.get("price")
                    if not price or price < PRICE_MIN or price > PRICE_MAX:
                        continue
                    city = str(p.get("city") or "").split(",")[0].strip().title() or "Inconnu"
                    rows.append({
                        "price": float(price),
                        "surface": float(p["surface_area"]) if p.get("surface_area") else None,
                        "beds": int(p["bedrooms"]) if p.get("bedrooms") else None,
                        "baths": int(p["bathrooms"]) if p.get("bathrooms") else None,
                        "city": city,
                        "type": _clean_type(p.get("property_type")),
                        "source": src,
                        "txn": _txn(p),
                        "title": str(p.get("title") or "")[:50],
                    })
            except Exception as e:
                logger.error(f"Source {src}: {e}")
        if not rows:
            return _demo_data()
        logger.info(f"Dashboard: {len(rows)} annonces chargees")
        return rows
    except Exception as e:
        logger.error(f"_load_data: {e}")
        return _demo_data()


def _demo_data():
    import random; random.seed(42)
    cities = ["Dakar","Almadies","Ngor","Ouakam","Mermoz","Pikine","Fann","Yoff","Plateau","Sicap"]
    types = ["Villa","Appartement","Terrain","Duplex","Studio","Maison"]
    sources = ["coinafrique","expat_dakar","loger_dakar","dakarvente"]
    rows = []
    for _ in range(2000):
        rows.append({
            "price": random.lognormvariate(17.8, 1.2),
            "surface": random.lognormvariate(4.5, 0.9),
            "beds": random.randint(1,6),
            "baths": random.randint(1,3),
            "city": random.choice(cities),
            "type": random.choice(types),
            "source": random.choice(sources),
            "txn": random.choice(["Vente","Location"]),
            "title": "Demo",
        })
    return rows


def _fmt(p):
    if not p or p < 1000: return "—"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds"
    if p >= 1e6:  return f"{p/1e6:.1f}M"
    if p >= 1e3:  return f"{p/1e3:.0f}K"
    return f"{p:,.0f}"


def _ctx(request):
    from immoanalytics_dash.views import get_user_role
    return {"user": request.user, "role": get_user_role(request.user)}


@login_required(login_url='/immo/login/')
def dashboard_page(request):
    txn_f = request.GET.get("txn", "all")
    src_f = request.GET.get("src", "all")
    type_f = request.GET.get("type", "all")
    city_f = request.GET.get("city", "")

    all_data = _load_data()
    sources_list = sorted(set(r["source"] for r in all_data))
    types_list = sorted(set(r["type"] for r in all_data if r["type"] != "Autre"))
    cities_list = sorted(set(r["city"] for r in all_data if r["city"] != "Inconnu"))[:80]

    # Apply filters
    data = all_data
    if txn_f != "all": data = [r for r in data if r["txn"] == txn_f]
    if src_f != "all": data = [r for r in data if r["source"] == src_f]
    if type_f != "all": data = [r for r in data if r["type"] == type_f]
    if city_f: data = [r for r in data if r["city"] == city_f]

    ventes = [r for r in data if r["txn"] == "Vente"]
    locations = [r for r in data if r["txn"] == "Location"]
    total = len(data); nv = len(ventes); nl = len(locations)

    prices_v = [r["price"] for r in ventes]
    prices_all = [r["price"] for r in data]
    pmed = _stats.median(prices_v) if prices_v else 0
    pmoy = _stats.mean(prices_v) if prices_v else 0

    # KPIs
    kpis = [
        {"label":"Annonces totales","value":f"{total:,}","color":"#0C2D4D","icon":"fas fa-database","sub":f"{nv} ventes - {nl} locations"},
        {"label":"Prix median vente","value":_fmt(pmed)+" FCFA" if pmed else "—","color":"#1A8ED8","icon":"fas fa-tag","sub":"Valeur centrale"},
        {"label":"Prix moyen vente","value":_fmt(pmoy)+" FCFA" if pmoy else "—","color":"#1B7A50","icon":"fas fa-chart-line","sub":"Moyenne"},
        {"label":"Sources actives","value":str(len(set(r["source"] for r in data))),"color":"#2563EB","icon":"fas fa-layer-group","sub":"Plateformes"},
        {"label":"Types de biens","value":str(len(set(r["type"] for r in data))),"color":"#7C3AED","icon":"fas fa-home","sub":"Categories"},
        {"label":"Villes couvertes","value":str(len(set(r["city"] for r in data if r["city"]!="Inconnu"))),"color":"#0891B2","icon":"fas fa-map-pin","sub":"Quartiers"},
    ]

    # === CHART DATA (raw arrays for JS) ===

    # 1. Price distribution (vente) - histogram bins
    dist_prices = sorted([r["price"]/1e6 for r in ventes if r["price"] >= 500_000 and r["price"] <= 1e9])

    # 2. Source pie
    src_counts = Counter(r["source"] for r in all_data)
    pie_labels = [s.replace("_"," ").title() for s in src_counts.keys()]
    pie_values = list(src_counts.values())
    pie_colors = [SRC_COLORS.get(s, "#999") for s in src_counts.keys()]

    # 3. Top cities by median price (vente)
    city_data = defaultdict(list)
    for r in ventes:
        if r["price"] >= 500_000 and r["city"] != "Inconnu":
            city_data[r["city"]].append(r["price"])
    top_cities = sorted(
        [(c, _stats.median(ps), len(ps)) for c, ps in city_data.items() if len(ps) >= 3],
        key=lambda x: x[1]
    )[-12:]
    cities_names = [c[0] for c in top_cities]
    cities_medians = [round(c[1]/1e6, 1) for c in top_cities]
    cities_counts = [c[2] for c in top_cities]

    # 4. Types bar
    type_counts = Counter(r["type"] for r in data if r["type"] != "Autre")
    types_top = type_counts.most_common(8)
    types_names = [t[0] for t in types_top]
    types_values = [t[1] for t in types_top]

    # 5. Vente vs Location by source
    txn_src = defaultdict(lambda: {"Vente":0,"Location":0})
    for r in all_data:
        txn_src[r["source"].replace("_"," ").title()][r["txn"]] += 1
    trend_labels = list(txn_src.keys())
    trend_vente = [txn_src[s]["Vente"] for s in trend_labels]
    trend_loc = [txn_src[s]["Location"] for s in trend_labels]

    # 6. Box plot data by type (top 5 types)
    box_data = {}
    for t in [t[0] for t in type_counts.most_common(5)]:
        ps = [r["price"]/1e6 for r in data if r["type"] == t and r["price"] >= 500_000]
        if len(ps) >= 3:
            box_data[t] = ps[:200]

    # 7. Scatter: price vs surface
    scatter_x = []
    scatter_y = []
    scatter_types = []
    for r in data:
        if r.get("surface") and 15 <= r["surface"] <= 3000 and r["price"] >= 500_000:
            scatter_x.append(round(r["surface"], 1))
            scatter_y.append(round(r["price"]/1e6, 1))
            scatter_types.append(r["type"])

    # 8. Price by bedrooms
    bed_data = defaultdict(list)
    for r in data:
        if r.get("beds") and 1 <= r["beds"] <= 8 and r["price"] >= 500_000:
            bed_data[r["beds"]].append(r["price"])
    bed_labels = []
    bed_medians = []
    for b in sorted(bed_data.keys()):
        if len(bed_data[b]) >= 3:
            bed_labels.append(f"{b} ch.")
            bed_medians.append(round(_stats.median(bed_data[b])/1e6, 1))

    # 9. Stats table
    stats_table = []
    if prices_all:
        s_prices = sorted(prices_all)
        n = len(s_prices)
        stats_table = [
            ("Annonces", f"{n:,}"),
            ("Prix minimum", _fmt(s_prices[0])+" FCFA"),
            ("1er quartile", _fmt(s_prices[n//4])+" FCFA"),
            ("Mediane", _fmt(s_prices[n//2])+" FCFA"),
            ("Moyenne", _fmt(_stats.mean(prices_all))+" FCFA"),
            ("3e quartile", _fmt(s_prices[3*n//4])+" FCFA"),
            ("Prix maximum", _fmt(s_prices[-1])+" FCFA"),
        ]

    # 10. Recent / top prices table
    recent = sorted(data, key=lambda x: x["price"], reverse=True)[:15]
    recent_rows = []
    for r in recent:
        recent_rows.append({
            "title": r["title"][:45] or r["city"],
            "price_fmt": _fmt(r["price"])+" FCFA",
            "city": r["city"],
            "type": r["type"],
            "source": r["source"].replace("_"," ").title(),
            "src_color": SRC_COLORS.get(r["source"], "#999"),
            "txn": r["txn"],
            "txn_color": "#1B7A50" if r["txn"] == "Vente" else "#2563EB",
        })

    # 11. Source median/mean prices
    src_price = defaultdict(list)
    for r in data:
        if r["price"] >= 500_000:
            src_price[r["source"].replace("_"," ").title()].append(r["price"])
    src_labels = []
    src_medians_v = []
    src_means_v = []
    for s, ps in sorted(src_price.items()):
        if len(ps) >= 3:
            src_labels.append(s)
            src_medians_v.append(round(_stats.median(ps)/1e6, 1))
            src_means_v.append(round(_stats.mean(ps)/1e6, 1))

    ctx = _ctx(request)
    ctx.update({
        "page_title": "Dashboard",
        "kpis": kpis,
        "recent_rows": recent_rows,
        "stats_table": stats_table,
        "sources_list": sources_list,
        "types_list": types_list,
        "cities_list": cities_list,
        "txn_f": txn_f, "src_f": src_f, "type_f": type_f, "city_f": city_f,
        "total": total, "nv": nv, "nl": nl,
        # Chart data as JSON strings (simple arrays, no Plotly objects)
        "j_dist": json.dumps(dist_prices[:500]),
        "j_pie_labels": json.dumps(pie_labels),
        "j_pie_values": json.dumps(pie_values),
        "j_pie_colors": json.dumps(pie_colors),
        "j_cities_names": json.dumps(cities_names),
        "j_cities_medians": json.dumps(cities_medians),
        "j_cities_counts": json.dumps(cities_counts),
        "j_types_names": json.dumps(types_names),
        "j_types_values": json.dumps(types_values),
        "j_trend_labels": json.dumps(trend_labels),
        "j_trend_vente": json.dumps(trend_vente),
        "j_trend_loc": json.dumps(trend_loc),
        "j_box": json.dumps(box_data),
        "j_scatter_x": json.dumps(scatter_x[:400]),
        "j_scatter_y": json.dumps(scatter_y[:400]),
        "j_scatter_t": json.dumps(scatter_types[:400]),
        "j_bed_labels": json.dumps(bed_labels),
        "j_bed_medians": json.dumps(bed_medians),
        "j_src_labels": json.dumps(src_labels),
        "j_src_medians": json.dumps(src_medians_v),
        "j_src_means": json.dumps(src_means_v),
    })
    return render(request, "immoanalytics/dashboard.html", ctx)


# Keep analytics_page as redirect to dashboard
@login_required(login_url='/immo/login/')
def analytics_page(request):
    from django.shortcuts import redirect
    return redirect('dashboard')


def api_stats_real(request):
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        models_map = {"coinafrique":CoinAfriqueProperty,"expat_dakar":ExpatDakarProperty,
                      "loger_dakar":LogerDakarProperty,"dakarvente":DakarVenteProperty}
        total=0; all_prices=[]
        for src,model in models_map.items():
            try:
                total += model.objects.count()
                for p in model.objects.filter(price__isnull=False,price__gt=0).values_list("price",flat=True)[:1000]:
                    if p: all_prices.append(float(p))
            except: pass
        p_med = _stats.median(all_prices) if all_prices else 0
        p_moy = _stats.mean(all_prices) if all_prices else 0
        return _JsonResponse({"total":total,"price_med":round(p_med),"price_avg":round(p_moy),
                               "price_med_fmt":_fmt(p_med),"price_avg_fmt":_fmt(p_moy)})
    except:
        return _JsonResponse({"total":0,"price_med":0,"price_avg":0})


def api_debug_db(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return _JsonResponse({"error":"Admin only"},status=403)
    from properties.models import (CoinAfriqueProperty,ExpatDakarProperty,
        LogerDakarProperty,DakarVenteProperty)
    result={"sources":{}}
    for name,model in [("coinafrique",CoinAfriqueProperty),("expat_dakar",ExpatDakarProperty),
                        ("loger_dakar",LogerDakarProperty),("dakarvente",DakarVenteProperty)]:
        try:
            total=model.objects.count()
            result["sources"][name]={"total":total,"with_price":model.objects.filter(price__isnull=False).count()}
        except Exception as e:
            result["sources"][name]={"error":str(e)[:80]}
    try:
        data=_load_data()
        result["loaded"]=len(data)
    except: pass
    return _JsonResponse(result,json_dumps_params={"indent":2})


# ── Prediction API (AJAX) ────────────────────────────────────────────────────

PRIX_REF = {
    ("chambre","location"):(30000,70000,150000),("studio","location"):(60000,120000,300000),
    ("appartement","location"):(150000,400000,1500000),("villa","location"):(300000,1200000,5000000),
    ("chambre","vente"):(500000,2000000,8000000),("studio","vente"):(2000000,8000000,25000000),
    ("appartement","vente"):(8000000,40000000,200000000),("villa","vente"):(20000000,100000000,500000000),
    ("terrain","vente"):(2000000,20000000,300000000),("maison","vente"):(5000000,30000000,150000000),
    ("duplex","vente"):(15000000,70000000,300000000),("immeuble","vente"):(50000000,200000000,2000000000),
}
ZONE_MULT = {
    "almadies":3.5,"ngor":3.0,"mermoz":2.5,"ouakam":2.0,"fann":2.2,"plateau":2.0,
    "yoff":1.8,"sacre coeur":2.3,"vdn":1.9,"point e":2.1,"mamelles":2.8,
    "sicap":1.5,"liberte":1.5,"hlm":1.3,"pikine":0.7,"guediawaye":0.65,
    "rufisque":0.55,"thies":0.5,"mbour":0.6,"saly":1.2,"dakar":1.0,
    "keur massar":0.6,"diamniadio":0.7,"parcelles":0.8,"medina":1.1,
}

@login_required(login_url='/immo/login/')
def api_predict(request):
    """API de prediction de prix (AJAX)."""
    if request.method != 'POST':
        return _JsonResponse({'error': 'POST requis'}, status=405)
    import json as _json
    try:
        body = _json.loads(request.body)
        city = body.get('city', '').strip()
        ptype = body.get('type', 'appartement').strip().lower()
        txn = body.get('transaction', 'vente').strip().lower()
        surface = float(body.get('surface', 0) or 0)
        beds = int(body.get('bedrooms', 0) or 0)

        # Try DB median first
        base = None
        try:
            from properties.models import (CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty)
            prices = []
            for model in [CoinAfriqueProperty, ExpatDakarProperty, LogerDakarProperty]:
                qs = model.objects.filter(price__gte=10000, price__lt=5000000000)
                if city: qs = qs.filter(city__icontains=city[:6])
                if ptype: qs = qs.filter(property_type__icontains=ptype[:5])
                prices.extend([float(p) for p in qs.values_list("price", flat=True)[:200] if p])
            if len(prices) >= 5:
                base = _stats.median(prices)
        except: pass

        if not base:
            ref = PRIX_REF.get((ptype, txn))
            if not ref:
                for k, v in PRIX_REF.items():
                    if k[0] == ptype: ref = v; break
            if not ref: ref = PRIX_REF.get(("appartement", txn), (1000000, 30000000, 100000000))
            base = ref[1]

        city_key = (city or "dakar").lower().strip()
        mult = next((v for k, v in ZONE_MULT.items() if k in city_key), 1.0)
        base *= mult

        if surface and surface > 0 and ptype not in ("chambre","terrain"):
            pm2 = {"appartement":400000,"villa":600000,"duplex":500000,"studio":450000}.get(ptype, 350000)
            if txn == "location": pm2 = pm2 // 180
            base = base * 0.4 + (surface * pm2 * mult) * 0.6

        if beds and beds > 1 and ptype not in ("chambre","studio","terrain"):
            base *= (1 + (beds - 1) * 0.05)

        base = max(base, 10000)
        margin = base * 0.20
        unit = "/mois" if txn == "location" else ""

        return _JsonResponse({
            'price': round(base),
            'price_fmt': _fmt(base) + " FCFA" + unit,
            'price_min': _fmt(max(base - margin, 10000)) + " FCFA",
            'price_max': _fmt(base + margin) + " FCFA",
            'model': f"Estimation statistique - {ptype} en {txn}",
            'confidence': "+/-20%",
        })
    except Exception as e:
        return _JsonResponse({'error': str(e)}, status=400)
