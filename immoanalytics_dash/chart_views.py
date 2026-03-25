"""
Vues Django pures pour Dashboard et Analytics.
Utilise Plotly Python pour générer les figures en JSON,
rendues côté client par plotly.js via CDN.
Pas de Dash, pas d'iframe, chargement instantané.
"""
import json, logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

PRICE_MIN = 1_000_000
PRICE_MAX = 5_000_000_000
C = {
    "gold":"#B8955A","dark":"#1A1A2E","green":"#1A5C3A","blue":"#2563EB",
    "red":"#C0392B","purple":"#7C3AED","muted":"#8B8680",
    "bg":"#F4F5F7","white":"#FFFFFF","border":"#E8EAF0",
    "src":{"coinafrique":"#F39C12","expat_dakar":"#2563EB",
           "loger_dakar":"#1A5C3A","dakarvente":"#C0392B"},
}
PAL = [C["gold"],C["blue"],C["green"],C["red"],C["purple"],"#F39C12","#16A085","#2C3E50"]

KW_LOC = ["louer","location","locat","bail","mensuel"]
KW_VTE = ["vendre","vente","achat","cession"]


def _txn(row):
    # Détection via statut/title si disponibles
    t = str(row.get("statut") or row.get("transaction") or "").lower()
    if any(k in t for k in ["vente","vendre","cession"]): return "Vente"
    if any(k in t for k in ["locat","louer","bail","mensuel"]): return "Location"
    txt = str(row.get("title") or "").lower()
    if any(k in txt for k in KW_LOC): return "Location"
    if any(k in txt for k in KW_VTE): return "Vente"
    # Fallback par prix : location < 2M FCFA/mois
    price = row.get("price", 0) or 0
    if 10_000 <= price <= 2_000_000: return "Location"
    return "Vente"


def _load_data(max_per_source=5000):
    """Charge les données depuis les 4 sources actives."""
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)

        SRCS = [
            (CoinAfriqueProperty, "coinafrique"),
            (ExpatDakarProperty,  "expat_dakar"),
            (LogerDakarProperty,  "loger_dakar"),
            (DakarVenteProperty,  "dakarvente"),
        ]
        BASE = ["id","price","surface_area","bedrooms","city","property_type"]
        dfs = []

        for model, src in SRCS:
            try:
                avail  = [f.name for f in model._meta.get_fields()]
                fields = [f for f in BASE if f in avail]
                # Charger SANS filtre prix — on filtre après
                rows = list(model.objects.values(*fields)[:max_per_source])
                if not rows:
                    logger.warning(f"{src}: 0 lignes retournées")
                    continue
                df = pd.DataFrame(rows)
                df["source"] = src
                dfs.append(df)
                logger.info(f"{src}: {len(rows)} lignes chargées")
            except Exception as e:
                logger.error(f"Erreur source {src}: {e}")
                continue

        if not dfs:
            logger.warning("Aucune source disponible -> démo")
            return _demo()

        df = pd.concat(dfs, ignore_index=True)

        # Conversions
        df["price"]        = pd.to_numeric(df["price"], errors="coerce")
        df["surface_area"] = pd.to_numeric(df.get("surface_area",
                             pd.Series(dtype=float)), errors="coerce")
        df["bedrooms"]     = pd.to_numeric(df.get("bedrooms",
                             pd.Series(dtype=float)), errors="coerce")
        df["city"]         = (df["city"].fillna("Inconnu").astype(str)
                              .str.split(",").str[0].str.strip().str.title())
        df["property_type"] = (df["property_type"].fillna("Autre")
                               .astype(str).str.strip().str.title())

        # Filtrer uniquement les prix nuls/négatifs
        df = df[df["price"].notna() & (df["price"] > 0)].copy()

        # Filtrer les prix aberrants : garder entre le 2e et 99e percentile
        if len(df) > 10:
            p_low  = df["price"].quantile(0.02)
            p_high = df["price"].quantile(0.99)
            df = df[df["price"].between(p_low, p_high)].copy()

        df["transaction"] = df.apply(_txn, axis=1)
        df["prix_m2"]     = df.apply(
            lambda r: r["price"] / r["surface_area"]
            if pd.notna(r.get("surface_area")) and r["surface_area"] > 10
            else None, axis=1)

        logger.info(f"_load_data: {len(df)} annonces valides")
        return df

    except Exception as e:
        logger.error(f"_load_data erreur globale: {e}")
        import traceback; traceback.print_exc()
        return _demo()


def _demo():
    """Données de démo réalistes — 4 sources, sans immosenegal."""
    rng = np.random.default_rng(42)
    cities  = ["Dakar","Almadies","Ngor","Ouakam","Mermoz","Pikine","Fann",
               "Yoff","Plateau","Sicap","Guediawaye","Rufisque","HLM",
               "Grand Yoff","Medina","Liberte","Thies","Mbour","Saly"]
    types   = ["Villa","Appartement","Terrain","Duplex","Studio","Maison"]
    # SEULEMENT les 4 sources actives
    sources = ["coinafrique","expat_dakar","loger_dakar","dakarvente"]
    n = 2000  # 2000 en démo (la vraie DB a 8000+)
    df = pd.DataFrame({
        "price":         np.clip(rng.lognormal(17.8, 1.2, n), 500_000, 2_000_000_000),
        "surface_area":  np.clip(rng.lognormal(4.5, .9, n), 20, 3000),
        "bedrooms":      rng.integers(1, 7, n).astype(float),
        "city":          rng.choice(cities, n),
        "property_type": rng.choice(types, n),
        "source":        rng.choice(sources, n),
        "transaction":   rng.choice(["Vente","Location"], n, p=[.6,.4]),
        "title":         ["Annonce"]*n,
    })
    df["prix_m2"] = df["price"] / df["surface_area"]
    return df


def _fmt(p):
    if not p or p < PRICE_MIN: return "—"
    if p >= 1e9: return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6: return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3: return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _gl():
    """Layout Plotly de base — fond blanc, police Inter."""
    return dict(
        paper_bgcolor=C["white"], plot_bgcolor=C["white"],
        font=dict(family="Inter,sans-serif", color=C["dark"], size=12),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(gridcolor=C["border"], linecolor=C["border"], zeroline=False),
        yaxis=dict(gridcolor=C["border"], linecolor=C["border"], zeroline=False),
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
    )


def _fig_json(fig):
    """Convertit une figure Plotly en JSON pour le template."""
    fig.update_layout(**_gl())
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def _ctx(request):
    from immoanalytics_dash.views import get_user_role
    return {"user": request.user, "role": get_user_role(request.user)}


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@login_required(login_url='/immo/login/')
def dashboard_page(request):
    txn_filter = request.GET.get("txn", "all")
    src_filter = request.GET.get("src", "all")

    df = _load_data()
    sources = sorted(df["source"].unique().tolist())

    if txn_filter != "all": df = df[df["transaction"] == txn_filter]
    if src_filter != "all": df = df[df["source"]      == src_filter]
    dv = df[df["transaction"] == "Vente"]

    total = len(df)
    nv    = len(dv)
    pmed  = float(dv["price"].median()) if nv > 0 else 0
    pmoy  = float(dv["price"].mean())   if nv > 0 else 0

    # ── KPIs ─────────────────────────────────────────────────────────────────
    pm2 = float(df["prix_m2"].mean()) if "prix_m2" in df.columns and df["prix_m2"].notna().any() else 0

    kpis = [
        {"label":"Annonces totales",  "value":f"{total:,}",                     "color":C["blue"],   "icon":"fas fa-database"},
        {"label":"Prix médian vente", "value":_fmt(pmed) if pmed else "—",       "color":C["gold"],   "icon":"fas fa-tag"},
        {"label":"Prix moyen vente",  "value":_fmt(pmoy) if pmoy else "—",       "color":C["green"],  "icon":"fas fa-chart-line"},
        {"label":"Sources actives",   "value":str(df["source"].nunique()),        "color":C["purple"], "icon":"fas fa-layer-group"},
        {"label":"Nombre de villas",   "value":f"{len(df[df['property_type'].str.lower().str.contains('villa', na=False)]):,}", "color":"#E67E22", "icon":"fas fa-home"},
    ]

    # ── Graphe 1 : Distribution des prix ─────────────────────────────────────
    if nv > 5:
        dp = dv[dv["price"].between(dv["price"].quantile(.02), dv["price"].quantile(.98))]
    else:
        dp = dv
    if len(dp) > 0:
        fig_dist = go.Figure(go.Histogram(
            x=dp["price"]/1e6, nbinsx=35,
            marker_color=C["gold"], marker_line_width=0,
            hovertemplate="Tranche : %{x:.0f}M FCFA<br>Annonces : %{y}<extra></extra>",
        ))
        fig_dist.update_xaxes(title_text="Prix (M FCFA)", ticksuffix="M")
        fig_dist.update_yaxes(title_text="Nombre d'annonces")
    else:
        fig_dist = go.Figure()
        fig_dist.add_annotation(text="Données insuffisantes", showarrow=False,
                                 font={"color":C["muted"],"size":14})

    # ── Graphe 2 : Donut sources ──────────────────────────────────────────────
    sc = df["source"].value_counts().reset_index(); sc.columns=["s","c"]
    fig_pie = go.Figure(go.Pie(
        labels=sc["s"].str.replace("_"," ").str.title(),
        values=sc["c"], hole=.52,
        marker_colors=[C["src"].get(s,"#BDC3C7") for s in sc["s"]],
        textinfo="percent+label", textfont={"size":11},
        hovertemplate="%{label}<br><b>%{value}</b> annonces (%{percent})<extra></extra>",
    ))
    fig_pie.update_layout(showlegend=False)

    # ── Graphe 3 : Top quartiers ──────────────────────────────────────────────
    top = (dv.groupby("city")["price"].agg(["median","count"])
           .query("count >= 3").sort_values("median",ascending=True).tail(10).reset_index())
    if len(top) > 0:
        fig_cities = go.Figure(go.Bar(
            x=top["median"]/1e6, y=top["city"], orientation="h",
            marker=dict(color=top["median"]/1e6,
                        colorscale=[[0,"#E8EAF0"],[1,C["gold"]]],showscale=False),
            text=[f"{v:.0f}M" for v in top["median"]/1e6], textposition="outside",
            hovertemplate="%{y}<br><b>%{x:.1f}M FCFA</b><br>%{customdata} annonces<extra></extra>",
            customdata=top["count"],
        ))
        fig_cities.update_xaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
        fig_cities.update_layout(margin=dict(l=10,r=60,t=30,b=40))
    else:
        fig_cities = go.Figure()
        fig_cities.add_annotation(text="Données insuffisantes", showarrow=False,
                                   font={"color":C["muted"],"size":14})

    # ── Graphe 4 : Types ─────────────────────────────────────────────────────
    tc = df["property_type"].value_counts().head(7).reset_index(); tc.columns=["t","c"]
    if len(tc) > 0:
        fig_types = go.Figure(go.Bar(
            x=tc["t"], y=tc["c"],
            marker_color=PAL[:len(tc)],
            text=tc["c"], textposition="outside",
            hovertemplate="%{x}<br><b>%{y}</b> annonces<extra></extra>",
        ))
        fig_types.update_xaxes(tickangle=-25)
        fig_types.update_yaxes(title_text="Annonces")
    else:
        fig_types = go.Figure()

    # ── Tableau ───────────────────────────────────────────────────────────────
    recent = df.nlargest(10, "price").to_dict("records")
    for r in recent:
        r["price_fmt"]  = _fmt(r.get("price",0))
        r["src_color"]  = C["src"].get(r.get("source",""), C["muted"])
        r["txn_color"]  = C["green"] if r.get("transaction")=="Vente" else C["blue"]
        r["title_short"]= str(r.get("title","") or "")[:45]

    ctx = _ctx(request)
    ctx.update({
        "page_title":   "Dashboard",
        "kpis":         kpis,
        "fig_dist":     _fig_json(fig_dist),
        "fig_pie":      _fig_json(fig_pie),
        "fig_cities":   _fig_json(fig_cities),
        "fig_types":    _fig_json(fig_types),
        "recent":       recent,
        "sources":      sources,
        "txn_filter":   txn_filter,
        "src_filter":   src_filter,
        "headers":      ["Titre","Prix","Ville","Type","Source","Transaction"],
    })
    return render(request, "immoanalytics/dashboard.html", ctx)


# ── ANALYTICS ─────────────────────────────────────────────────────────────────

@login_required(login_url='/immo/login/')
def analytics_page(request):
    txn_filter  = request.GET.get("txn",  "Vente")
    src_filter  = request.GET.get("src",  "all")
    type_filter = request.GET.get("type", "all")
    city_filter = request.GET.get("city", "")

    df = _load_data()
    sources = sorted(df["source"].unique().tolist())
    types   = sorted(df["property_type"].dropna().unique().tolist())
    cities  = sorted(df["city"].dropna().unique().tolist())

    if txn_filter != "all": df = df[df["transaction"]    == txn_filter]
    if src_filter != "all": df = df[df["source"]          == src_filter]
    if type_filter!= "all": df = df[df["property_type"]  == type_filter]
    if city_filter:         df = df[df["city"]            == city_filter]

    def empty_fig(msg="Données insuffisantes"):
        f = go.Figure()
        f.add_annotation(text=msg, showarrow=False, font={"color":C["muted"],"size":14})
        return f

    # ── Box plot ──────────────────────────────────────────────────────────────
    top5 = df["property_type"].value_counts().head(5).index.tolist()
    fig_box = go.Figure()
    for i, t in enumerate(top5):
        sub = df[df["property_type"]==t]["price"]
        if len(sub) >= 3:
            fig_box.add_trace(go.Box(
                y=sub/1e6, name=t, marker_color=PAL[i%len(PAL)],
                boxmean=True, line_width=1.5,
                hovertemplate=f"<b>{t}</b><br>%{{y:.1f}}M FCFA<extra></extra>",
            ))
    if not fig_box.data:
        fig_box = empty_fig()
    else:
        fig_box.update_yaxes(title_text="Prix (M FCFA)")
        fig_box.update_layout(showlegend=False)

    # ── Scatter prix / surface ────────────────────────────────────────────────
    dfs = df[df["surface_area"].between(15,2000) & df["price"].notna()].head(500)
    if len(dfs) > 5:
        dfs = dfs.copy()
        dfs["prix_M"] = dfs["price"] / 1e6
        fig_sc = px.scatter(
            dfs, x="surface_area", y="prix_M",
            color="property_type", color_discrete_sequence=PAL,
            labels={"surface_area":"Superficie (m²)","prix_M":"Prix (M FCFA)"},
            opacity=0.65,
        )
        fig_sc.update_traces(marker_size=5)
        fig_sc.update_yaxes(title_text="Prix (M FCFA)")
        fig_sc.update_xaxes(title_text="Superficie (m²)")
    else:
        fig_sc = empty_fig("Surface non renseignée")

    # ── Bar villes ────────────────────────────────────────────────────────────
    cs = (df.groupby("city")["price"].agg(["median","count"])
          .query("count >= 3").sort_values("median",ascending=True).tail(12).reset_index())
    if len(cs) > 0:
        fig_bar = go.Figure(go.Bar(
            x=cs["median"]/1e6, y=cs["city"], orientation="h",
            marker=dict(color=cs["median"]/1e6,
                        colorscale=[[0,"#E8EAF0"],[1,C["gold"]]],showscale=False),
            text=[f"{v:.0f}M" for v in cs["median"]/1e6], textposition="outside",
            hovertemplate="%{y}<br><b>%{x:.1f}M FCFA</b><br>%{customdata} ann.<extra></extra>",
            customdata=cs["count"],
        ))
        fig_bar.update_xaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
        fig_bar.update_layout(margin=dict(l=10,r=60,t=30,b=40))
    else:
        fig_bar = empty_fig()

    # ── Comparaison sources ───────────────────────────────────────────────────
    ss = df.groupby("source")["price"].agg(["median","mean","count"]).reset_index()
    ss = ss[ss["count"]>=3]
    if len(ss)>0:
        lbl = ss["source"].str.replace("_"," ").str.title()
        fig_src = go.Figure()
        fig_src.add_trace(go.Bar(name="Médiane",x=lbl,y=ss["median"]/1e6,
            marker_color=C["gold"],text=[f"{v:.0f}M" for v in ss["median"]/1e6],textposition="outside"))
        fig_src.add_trace(go.Bar(name="Moyenne",x=lbl,y=ss["mean"]/1e6,
            marker_color=C["blue"],text=[f"{v:.0f}M" for v in ss["mean"]/1e6],textposition="outside"))
        fig_src.update_layout(barmode="group",
                              legend=dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)"))
        fig_src.update_yaxes(title_text="Prix (M FCFA)", ticksuffix="M")
    else:
        fig_src = empty_fig()

    # ── Prix au m² ────────────────────────────────────────────────────────────
    if "prix_m2" in df.columns:
        dm2 = df[df["prix_m2"].between(50_000, 5_000_000)]
    else:
        dm2 = pd.DataFrame()
    if len(dm2)>5:
        fig_m2 = go.Figure(go.Histogram(
            x=dm2["prix_m2"]/1e3, nbinsx=35,
            marker_color=C["green"], marker_line_width=0,
            hovertemplate="Prix/m² : %{x:.0f}K FCFA<br>Annonces : %{y}<extra></extra>",
        ))
        fig_m2.update_xaxes(title_text="Prix au m² (K FCFA)",ticksuffix="K")
        fig_m2.update_yaxes(title_text="Annonces")
    else:
        fig_m2 = empty_fig("Surface non renseignée")

    # ── Stats descriptives ────────────────────────────────────────────────────
    s = df["price"].describe() if len(df)>0 else pd.Series(dtype=float)
    stats = []
    if len(s)>0:
        stats = [
            ("Nombre d'annonces",  f"{int(s.get('count',0)):,}"),
            ("Prix minimum",       _fmt(s.get("min",0))),
            ("1er quartile",       _fmt(s.get("25%",0))),
            ("Médiane",            _fmt(s.get("50%",0))),
            ("Moyenne",            _fmt(s.get("mean",0))),
            ("3e quartile",        _fmt(s.get("75%",0))),
            ("Prix maximum",       _fmt(s.get("max",0))),
        ]

    ctx = _ctx(request)
    ctx.update({
        "page_title":   "Analytics",
        "fig_box":      _fig_json(fig_box),
        "fig_sc":       _fig_json(fig_sc),
        "fig_bar":      _fig_json(fig_bar),
        "fig_src":      _fig_json(fig_src),
        "fig_m2":       _fig_json(fig_m2),
        "stats":        stats,
        "sources":      sources,
        "types":        types,
        "cities":       cities,
        "txn_filter":   txn_filter,
        "src_filter":   src_filter,
        "type_filter":  type_filter,
        "city_filter":  city_filter,
    })
    return render(request, "immoanalytics/analytics.html", ctx)


# ═══════════════════════════════════════════════════════════
# API : statistiques réelles (landing page + about)
# ═══════════════════════════════════════════════════════════

from django.http import JsonResponse as _JsonResponse

def api_stats_real(request):
    """Statistiques réelles de la DB pour la page d'accueil."""
    try:
        from properties.models import (
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty,
        )
        import statistics as _stats

        models_map = {
            "coinafrique":  CoinAfriqueProperty,
            "expat_dakar":  ExpatDakarProperty,
            "loger_dakar":  LogerDakarProperty,
            "dakarvente":   DakarVenteProperty,

        }
        total = 0
        all_prices = []
        cities_set = set()

        for src, model in models_map.items():
            total += model.objects.count()
            for p in model.objects.filter(
                price__isnull=False, price__gt=0
            ).values_list("price", flat=True)[:1000]:
                if p: all_prices.append(float(p))
            for c in model.objects.values_list("city", flat=True).distinct()[:20]:
                if c and c.strip():
                    cities_set.add(c.strip().split(",")[0].strip().title())

        p_med = _stats.median(all_prices) if all_prices else 0
        p_moy = _stats.mean(all_prices)   if all_prices else 0

        return _JsonResponse({
            "total": total, "sources": len(models_map),
            "cities": len(cities_set),
            "price_med": round(p_med), "price_avg": round(p_moy),
            "price_med_fmt": _fmt(p_med), "price_avg_fmt": _fmt(p_moy),
        })
    except Exception as e:
        logger.warning(f"api_stats_real: {e}")
        return _JsonResponse({
            "total": 0, "sources": 5, "cities": 0,
            "price_med": 0, "price_avg": 0,
            "price_med_fmt": "—", "price_avg_fmt": "—",
        })


@login_required(login_url='/immo/login/')
def api_debug_db(request):
    """Debug : etat de la DB — tables, comptages, echantillons de prix."""
    if not request.user.is_superuser:
        return _JsonResponse({"error": "Admin seulement"}, status=403)

    from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
        LogerDakarProperty, DakarVenteProperty)

    result = {"sources": {}, "tables_manquantes": [], "_load_data_count": 0}

    for name, model in [
        ("coinafrique", CoinAfriqueProperty),
        ("expat_dakar", ExpatDakarProperty),
        ("loger_dakar", LogerDakarProperty),
        ("dakarvente",  DakarVenteProperty),
    ]:
        try:
            total      = model.objects.count()
            with_price = model.objects.filter(price__isnull=False).count()
            sample     = list(model.objects.filter(
                price__isnull=False
            ).values_list("price", flat=True)[:5])
            result["sources"][name] = {
                "status":        "OK",
                "total":         total,
                "with_price":    with_price,
                "sample_prices": [float(p) for p in sample if p],
            }
        except Exception as e:
            result["sources"][name] = {
                "status": "TABLE MANQUANTE",
                "detail": str(e).split("\n")[0],
            }
            result["tables_manquantes"].append(name)

    try:
        df = _load_data()
        result["_load_data_count"] = len(df)
        if len(df) > 0:
            result["_load_data_sources"] = df["source"].value_counts().to_dict()
    except Exception as e:
        result["_load_data_error"] = str(e)

    if result["tables_manquantes"]:
        result["conseil"] = (
            "Tables manquantes: " + str(result["tables_manquantes"]) +
            ". Lancez les scrapers correspondants."
        )

    return _JsonResponse(result, json_dumps_params={"indent": 2})