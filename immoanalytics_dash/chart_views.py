"""
ImmoPredict SN — chart_views.py
Vues Django pures pour Dashboard et Analytics.
Plotly Python → JSON → rendu Plotly.js CDN.
Tous les graphes garantis fonctionnels.
"""
import json, logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
PRICE_MIN = 1_000_000
PRICE_MAX = 5_000_000_000
C = {
    "gold":   "#C9A84C",
    "navy":   "#0F2444",
    "green":  "#0E6B4A",
    "blue":   "#2563EB",
    "red":    "#C0392B",
    "purple": "#7C3AED",
    "teal":   "#0891B2",
    "muted":  "#6B7280",
    "bg":     "#F5F6FA",
    "white":  "#FFFFFF",
    "border": "#DDE1EE",
    "src": {
        "coinafrique":  "#F59E0B",
        "expat_dakar":  "#2563EB",
        "loger_dakar":  "#0E6B4A",
        "dakarvente":   "#C0392B",
        "immosenegal":  "#7C3AED",
        "2simmobilier": "#0891B2",
    },
}
PAL = [C["gold"], C["blue"], C["green"], C["red"], C["purple"], C["teal"], "#F59E0B", "#16A085"]
KW_LOC = ["louer","location","locat","bail","mensuel","loyer"]
KW_VTE = ["vendre","vente","achat","cession"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ctx(request):
    from immoanalytics_dash.views import get_user_role
    return {"user": request.user, "role": get_user_role(request.user)}


def _txn(row):
    t = str(row.get("statut") or row.get("transaction") or "").lower()
    if any(k in t for k in ["vente","vendre"]): return "Vente"
    if any(k in t for k in ["locat","louer"]):  return "Location"
    txt = str(row.get("title") or "").lower()
    if any(k in txt for k in KW_LOC): return "Location"
    if any(k in txt for k in KW_VTE): return "Vente"
    return "Autre"


def _load_data(max_rows=3000):
    """Charge les données depuis toutes les sources DB."""
    try:
        from properties.models import (
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty,
        )
        SRCS = [
            (CoinAfriqueProperty,  "coinafrique",  ["latitude","longitude"]),
            (ExpatDakarProperty,   "expat_dakar",  []),
            (LogerDakarProperty,   "loger_dakar",  []),
            (DakarVenteProperty,   "dakarvente",   ["latitude","longitude"]),
            (ImmoSenegalProperty,  "immosenegal",  ["transaction"]),
        ]
        BASE = ["id","price","surface_area","bedrooms","bathrooms",
                "city","property_type","statut","title","scraped_at"]
        dfs = []
        per_src = max(max_rows // len(SRCS), 500)
        for model, src, extra in SRCS:
            avail  = [f.name for f in model._meta.get_fields()]
            fields = [f for f in BASE + extra if f in avail]
            rows   = list(model.objects.filter(
                price__gte=PRICE_MIN, price__lte=PRICE_MAX
            ).values(*fields)[:per_src])
            if not rows: continue
            df = pd.DataFrame(rows); df["source"] = src; dfs.append(df)
        if not dfs: return _demo()
        df = pd.concat(dfs, ignore_index=True)
        return _clean(df)
    except Exception as e:
        logger.warning(f"DB load: {e}")
        return _demo()


def _clean(df):
    df["price"]        = pd.to_numeric(df["price"], errors="coerce")
    df["surface_area"] = pd.to_numeric(df["surface_area"], errors="coerce")
    df["bedrooms"]     = pd.to_numeric(df.get("bedrooms", pd.Series(dtype=float)), errors="coerce")
    df["city"]         = (df["city"].fillna("Inconnu").astype(str)
                          .str.split(",").str[0].str.strip().str.title())
    df["property_type"]= df["property_type"].fillna("Autre").astype(str).str.strip().str.title()
    df = df[df["price"].notna() & (df["price"] >= PRICE_MIN)].copy()
    df["transaction"]  = df.apply(_txn, axis=1)
    df["prix_m2"]      = df.apply(
        lambda r: r["price"]/r["surface_area"]
        if pd.notna(r.get("surface_area")) and r["surface_area"] > 10 else None, axis=1)
    return df


def _demo():
    """Données de démo si DB vide."""
    rng = np.random.default_rng(42)
    cities  = ["Dakar","Almadies","Ngor","Ouakam","Mermoz","Pikine","Fann","Yoff","Plateau","Sicap","Guédiawaye","Rufisque"]
    types   = ["Villa","Appartement","Terrain","Duplex","Studio","Maison"]
    sources = list(C["src"].keys())
    n = 800
    df = pd.DataFrame({
        "price":         np.clip(rng.lognormal(17.8,1.2,n), 2e6, 8e8),
        "surface_area":  np.clip(rng.lognormal(4.5,.9,n), 20, 3000),
        "bedrooms":      rng.integers(1,7,n).astype(float),
        "city":          rng.choice(cities, n),
        "property_type": rng.choice(types, n),
        "source":        rng.choice(sources, n),
        "transaction":   rng.choice(["Vente","Location"], n, p=[.6,.4]),
        "title":         ["Annonce"]*n,
    })
    df["prix_m2"] = df["price"]/df["surface_area"]
    return df


def _fmt(p):
    if not p or float(p) < 1000: return "—"
    p = float(p)
    if p >= 1e9:  return f"{p/1e9:.2f} Mds FCFA"
    if p >= 1e6:  return f"{p/1e6:.1f}M FCFA"
    if p >= 1e3:  return f"{p/1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _gl(margins=None, show_legend=True):
    """Layout Plotly standard."""
    m = margins or {"l":40, "r":20, "t":30, "b":40}
    return dict(
        paper_bgcolor=C["white"], plot_bgcolor=C["white"],
        font=dict(family="Inter,sans-serif", color=C["navy"], size=11.5),
        margin=m,
        xaxis=dict(gridcolor=C["border"], linecolor=C["border"], zeroline=False),
        yaxis=dict(gridcolor=C["border"], linecolor=C["border"], zeroline=False),
        legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15),
        showlegend=show_legend,
    )


def _fig_json(fig):
    fig.update_layout(**_gl())
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def _empty(msg="Données insuffisantes"):
    f = go.Figure()
    f.add_annotation(
        text=f'<i class="fa fa-exclamation"></i> {msg}',
        showarrow=False,
        font=dict(size=13, color=C["muted"]),
        x=0.5, y=0.5, xref="paper", yref="paper"
    )
    f.update_layout(**_gl())
    return f


# ═══════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════

@login_required(login_url='/immo/login/')
def dashboard_page(request):
    txn_f = request.GET.get("txn", "all")
    src_f = request.GET.get("src", "all")

    df_full = _load_data()
    sources = sorted(df_full["source"].unique().tolist())
    types   = sorted(df_full["property_type"].dropna().unique().tolist())

    df = df_full.copy()
    if txn_f != "all": df = df[df["transaction"] == txn_f]
    if src_f != "all": df = df[df["source"]      == src_f]
    dv = df[df["transaction"] == "Vente"]
    dl = df[df["transaction"] == "Location"]

    total = len(df)
    nv    = len(dv)
    nl    = len(dl)
    pmed  = float(dv["price"].median()) if nv > 0 else 0
    pmoy  = float(dv["price"].mean())   if nv > 0 else 0
    pm2   = float(dv["prix_m2"].median()) if "prix_m2" in dv.columns and nv > 0 else 0
    nvilla= len(df[df["property_type"].str.lower().str.contains("villa", na=False)])

    # KPIs
    kpis = [
        {"label":"Annonces totales",  "value":f"{total:,}",                          "color":C["navy"],   "icon":"fas fa-database",     "sub":f"{nv} ventes · {nl} locations"},
        {"label":"Prix médian vente", "value":_fmt(pmed) if pmed else "—",            "color":C["gold"],   "icon":"fas fa-tag",           "sub":"Valeur centrale"},
        {"label":"Prix moyen vente",  "value":_fmt(pmoy) if pmoy else "—",            "color":C["green"],  "icon":"fas fa-chart-line",    "sub":"Moyenne arithmétique"},
        {"label":"Sources de données","value":str(df["source"].nunique()),             "color":C["blue"],   "icon":"fas fa-layer-group",   "sub":"Plateformes actives"},
        {"label":"Villas disponibles","value":f"{nvilla:,}",                          "color":C["purple"], "icon":"fas fa-home",          "sub":"Sur tout le territoire"},
        {"label":"Prix/m² médian",    "value":f"{_fmt(pm2)}/m²" if pm2 else "—",     "color":C["teal"],   "icon":"fas fa-expand",        "sub":"Vente uniquement"},
    ]

    # ── Graphe 1 : Distribution des prix ────────────────────────────────────
    if nv > 5:
        dp = dv[dv["price"].between(dv["price"].quantile(.02), dv["price"].quantile(.98))]
    else:
        dp = dv
    if len(dp) > 0:
        fig_dist = go.Figure(go.Histogram(
            x=dp["price"]/1e6, nbinsx=40,
            marker_color=C["gold"], marker_line_width=0, marker_line_color=C["white"],
            hovertemplate="Tranche : %{x:.0f}M FCFA<br>Annonces : %{y}<extra></extra>",
            name="Distribution",
        ))
        fig_dist.update_xaxes(title_text="Prix (M FCFA)", ticksuffix="M")
        fig_dist.update_yaxes(title_text="Annonces")
    else:
        fig_dist = _empty("Aucune donnée de vente")

    # ── Graphe 2 : Donut sources ─────────────────────────────────────────────
    sc = df["source"].value_counts().reset_index(); sc.columns = ["s","c"]
    colors_src = [C["src"].get(s, "#999") for s in sc["s"]]
    fig_pie = go.Figure(go.Pie(
        labels=sc["s"].str.replace("_"," ").str.title(),
        values=sc["c"], hole=.55,
        marker_colors=colors_src,
        textinfo="percent+label", textfont=dict(size=10),
        hovertemplate="%{label}<br><b>%{value}</b> annonces (%{percent})<extra></extra>",
    ))
    fig_pie.update_layout(showlegend=False)

    # ── Graphe 3 : Top 10 quartiers prix médian ──────────────────────────────
    top_q = (dv.groupby("city")["price"].agg(["median","count"])
               .query("count >= 3")
               .sort_values("median", ascending=True)
               .tail(12).reset_index())
    if len(top_q) > 0:
        fig_cities = go.Figure(go.Bar(
            x=top_q["median"]/1e6, y=top_q["city"], orientation="h",
            marker=dict(
                color=top_q["median"]/1e6,
                colorscale=[[0,"#E8EAF0"],[0.5,C["gold"]+"80"],[1,C["gold"]]],
                showscale=False,
            ),
            text=[f"{v:.0f}M" for v in top_q["median"]/1e6],
            textposition="outside",
            hovertemplate="%{y}<br><b>%{x:.1f}M FCFA</b><br>%{customdata} ann.<extra></extra>",
            customdata=top_q["count"],
        ))
        fig_cities.update_xaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
        fig_cities.update_layout(margin=dict(l=10,r=60,t=15,b=30))
    else:
        fig_cities = _empty()

    # ── Graphe 4 : Types de biens ────────────────────────────────────────────
    tc = df["property_type"].value_counts().head(8).reset_index(); tc.columns=["t","c"]
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
        fig_types = _empty()

    # ── Graphe 5 : Évolution temporelle (si scraped_at disponible) ───────────
    fig_trend = _empty("Données temporelles non disponibles")
    try:
        if "scraped_at" in df.columns:
            df_t = df.copy()
            df_t["scraped_at"] = pd.to_datetime(df_t["scraped_at"], errors="coerce")
            df_t = df_t.dropna(subset=["scraped_at"])
            if len(df_t) > 50:
                monthly = df_t.groupby(df_t["scraped_at"].dt.to_period("M")).agg(
                    count=("price","count"),
                    med_price=("price","median")
                ).reset_index()
                monthly["month"] = monthly["scraped_at"].astype(str)
                from plotly.subplots import make_subplots
                fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
                fig_trend.add_trace(go.Bar(
                    x=monthly["month"], y=monthly["count"],
                    name="Annonces", marker_color=C["teal"]+"80",
                ), secondary_y=False)
                fig_trend.add_trace(go.Scatter(
                    x=monthly["month"], y=monthly["med_price"]/1e6,
                    name="Prix médian", line=dict(color=C["gold"],width=2.5),
                    mode="lines+markers",
                ), secondary_y=True)
                fig_trend.update_yaxes(title_text="Annonces", secondary_y=False)
                fig_trend.update_yaxes(title_text="Prix médian (M)", ticksuffix="M", secondary_y=True)
    except Exception as e:
        logger.warning(f"Trend: {e}")

    # ── Tableau : annonces récentes prix élevés ──────────────────────────────
    recent = df.nlargest(12, "price").to_dict("records")
    for r in recent:
        r["price_fmt"] = _fmt(r.get("price",0))
        r["src_color"] = C["src"].get(r.get("source",""), C["muted"])
        r["txn_color"] = C["green"] if r.get("transaction")=="Vente" else C["blue"]
        r["title_sh"]  = str(r.get("title","") or "")[:48]
        r["city"]      = str(r.get("city","") or "—")
        r["prop_type"] = str(r.get("property_type","") or "—")

    ctx = _ctx(request)
    ctx.update({
        "page_title":  "Dashboard",
        "kpis":        kpis,
        "fig_dist":    _fig_json(fig_dist),
        "fig_pie":     _fig_json(fig_pie),
        "fig_cities":  _fig_json(fig_cities),
        "fig_types":   _fig_json(fig_types),
        "fig_trend":   _fig_json(fig_trend),
        "recent":      recent,
        "sources":     sources,
        "types":       types,
        "txn_filter":  txn_f,
        "src_filter":  src_f,
        "headers":     ["Titre","Prix","Ville","Type","Source","Transaction"],
        "total":       total, "nv": nv, "nl": nl,
    })
    return render(request, "immoanalytics/dashboard.html", ctx)


# ═══════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════

@login_required(login_url='/immo/login/')
def analytics_page(request):
    txn_f  = request.GET.get("txn",  "Vente")
    src_f  = request.GET.get("src",  "all")
    type_f = request.GET.get("type", "all")
    city_f = request.GET.get("city", "")

    df_full = _load_data()
    sources = sorted(df_full["source"].unique().tolist())
    types   = sorted(df_full["property_type"].dropna().unique().tolist())
    cities  = sorted(df_full["city"].dropna().unique().tolist())

    df = df_full.copy()
    if txn_f != "all": df = df[df["transaction"]    == txn_f]
    if src_f != "all": df = df[df["source"]          == src_f]
    if type_f!= "all": df = df[df["property_type"]  == type_f]
    if city_f:         df = df[df["city"]            == city_f]

    # ── Box plot distribution par type ───────────────────────────────────────
    top5 = df["property_type"].value_counts().head(5).index.tolist()
    fig_box = go.Figure()
    for i, t in enumerate(top5):
        sub = df[df["property_type"] == t]["price"]
        if len(sub) >= 3:
            fig_box.add_trace(go.Box(
                y=sub/1e6, name=t, marker_color=PAL[i % len(PAL)],
                boxmean=True, line_width=1.5, boxpoints="outliers",
                hovertemplate=f"<b>{t}</b><br>%{{y:.1f}}M FCFA<extra></extra>",
            ))
    if not fig_box.data:
        fig_box = _empty("Données insuffisantes pour le box plot")
    else:
        fig_box.update_yaxes(title_text="Prix (M FCFA)")
        fig_box.update_layout(showlegend=False)

    # ── Scatter prix vs surface ──────────────────────────────────────────────
    dfs = df[df["surface_area"].between(15, 3000) & df["price"].notna()].copy()
    dfs["prix_M"] = dfs["price"] / 1e6
    if len(dfs) > 5:
        fig_sc = px.scatter(
            dfs.head(600), x="surface_area", y="prix_M",
            color="property_type", color_discrete_sequence=PAL,
            labels={"surface_area":"Superficie (m²)","prix_M":"Prix (M FCFA)"},
            opacity=0.65, trendline="ols" if len(dfs) > 20 else None,
        )
        fig_sc.update_traces(marker_size=5)
        fig_sc.update_yaxes(title_text="Prix (M FCFA)")
        fig_sc.update_xaxes(title_text="Superficie (m²)")
    else:
        fig_sc = _empty("Surface non renseignée")

    # ── Bar prix médian par ville ────────────────────────────────────────────
    cs = (df.groupby("city")["price"].agg(["median","count","mean"])
            .query("count >= 3")
            .sort_values("median", ascending=True)
            .tail(15).reset_index())
    if len(cs) > 0:
        fig_bar = go.Figure(go.Bar(
            x=cs["median"]/1e6, y=cs["city"], orientation="h",
            marker=dict(
                color=cs["median"]/1e6,
                colorscale=[[0,"#EEF0F8"],[1,C["gold"]]],
                showscale=False,
            ),
            text=[f"{v:.0f}M" for v in cs["median"]/1e6],
            textposition="outside",
            hovertemplate="%{y}<br>Médiane: <b>%{x:.1f}M FCFA</b><br>%{customdata} ann.<extra></extra>",
            customdata=cs["count"],
        ))
        fig_bar.update_xaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
        fig_bar.update_layout(margin=dict(l=10,r=70,t=15,b=30))
    else:
        fig_bar = _empty()

    # ── Comparaison sources médiane vs moyenne ───────────────────────────────
    ss = df.groupby("source")["price"].agg(["median","mean","count"]).reset_index()
    ss = ss[ss["count"] >= 3]
    if len(ss) > 0:
        lbl = ss["source"].str.replace("_"," ").str.title()
        fig_src = go.Figure()
        fig_src.add_trace(go.Bar(
            name="Médiane", x=lbl, y=ss["median"]/1e6,
            marker_color=C["gold"],
            text=[f"{v:.0f}M" for v in ss["median"]/1e6], textposition="outside",
        ))
        fig_src.add_trace(go.Bar(
            name="Moyenne", x=lbl, y=ss["mean"]/1e6,
            marker_color=C["blue"],
            text=[f"{v:.0f}M" for v in ss["mean"]/1e6], textposition="outside",
        ))
        fig_src.update_layout(
            barmode="group",
            legend=dict(orientation="h", y=-0.2, bgcolor="rgba(0,0,0,0)"),
        )
        fig_src.update_yaxes(title_text="Prix (M FCFA)", ticksuffix="M")
    else:
        fig_src = _empty()

    # ── Distribution prix/m² ─────────────────────────────────────────────────
    if "prix_m2" in df.columns:
        dm2 = df[df["prix_m2"].between(50_000, 8_000_000)].copy()
    else:
        dm2 = pd.DataFrame()
    if len(dm2) > 5:
        fig_m2 = go.Figure(go.Histogram(
            x=dm2["prix_m2"]/1e3, nbinsx=40,
            marker_color=C["green"], marker_line_width=0,
            hovertemplate="Prix/m² : %{x:.0f}K FCFA<br>Annonces : %{y}<extra></extra>",
        ))
        fig_m2.update_xaxes(title_text="Prix au m² (K FCFA)", ticksuffix="K")
        fig_m2.update_yaxes(title_text="Annonces")
    else:
        fig_m2 = _empty("Surface non renseignée")

    # ── Corrélation chambres / prix ──────────────────────────────────────────
    dbc = df[df["bedrooms"].between(1, 10) & df["price"].notna()].copy()
    if len(dbc) > 5:
        bed_stats = dbc.groupby("bedrooms")["price"].agg(["median","count"]).reset_index()
        bed_stats = bed_stats[bed_stats["count"] >= 3]
        fig_beds = go.Figure(go.Bar(
            x=[f"{int(b)} ch." for b in bed_stats["bedrooms"]],
            y=bed_stats["median"]/1e6,
            marker_color=PAL,
            text=[f"{v:.0f}M" for v in bed_stats["median"]/1e6],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Prix médian : %{y:.1f}M FCFA<extra></extra>",
        ))
        fig_beds.update_yaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
    else:
        fig_beds = _empty("Données chambres insuffisantes")

    # ── Stats descriptives ───────────────────────────────────────────────────
    stats_data = []
    if len(df) > 0:
        s = df["price"].describe()
        stats_data = [
            ("Annonces", f"{int(s.get('count',0)):,}"),
            ("Prix minimum",    _fmt(s.get("min",0))),
            ("1er quartile",    _fmt(s.get("25%",0))),
            ("Médiane",         _fmt(s.get("50%",0))),
            ("Moyenne",         _fmt(s.get("mean",0))),
            ("3e quartile",     _fmt(s.get("75%",0))),
            ("Prix maximum",    _fmt(s.get("max",0))),
            ("Écart-type",      _fmt(s.get("std",0))),
            ("Coefficient var.",f"{s.get('std',0)/s.get('mean',1)*100:.1f}%"),
        ]

    ctx = _ctx(request)
    ctx.update({
        "page_title":  "Analytics",
        "fig_box":     _fig_json(fig_box),
        "fig_sc":      _fig_json(fig_sc),
        "fig_bar":     _fig_json(fig_bar),
        "fig_src":     _fig_json(fig_src),
        "fig_m2":      _fig_json(fig_m2),
        "fig_beds":    _fig_json(fig_beds),
        "stats":       stats_data,
        "sources":     sources,
        "types":       types,
        "cities":      cities,
        "txn_filter":  txn_f,
        "src_filter":  src_f,
        "type_filter": type_f,
        "city_filter": city_f,
    })
    return render(request, "immoanalytics/analytics.html", ctx)


# ═══════════════════════════════════════════════════════════
# API : statistiques réelles pour la landing page
# ═══════════════════════════════════════════════════════════

def api_stats_real(request):
    """Retourne les vraies statistiques pour la page d'accueil."""
    try:
        from properties.models import (
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty,
        )
        from django.db.models import Avg, Count
        import statistics

        models_map = {
            "coinafrique":  CoinAfriqueProperty,
            "expat_dakar":  ExpatDakarProperty,
            "loger_dakar":  LogerDakarProperty,
            "dakarvente":   DakarVenteProperty,
            "immosenegal":  ImmoSenegalProperty,
        }

        total = 0
        all_prices = []
        cities_set = set()

        for src, model in models_map.items():
            count = model.objects.count()
            total += count
            prices = list(model.objects.filter(
                price__gte=PRICE_MIN, price__lte=PRICE_MAX
            ).values_list("price", flat=True)[:500])
            all_prices.extend([float(p) for p in prices if p])
            for c in model.objects.values_list("city", flat=True).distinct()[:20]:
                if c and c.strip():
                    cities_set.add(c.strip().split(",")[0].strip().title())

        p_med = statistics.median(all_prices) if all_prices else 0
        p_moy = statistics.mean(all_prices)   if all_prices else 0

        return JsonResponse({
            "total":       total,
            "sources":     len(models_map),
            "cities":      len(cities_set),
            "price_med":   round(p_med),
            "price_avg":   round(p_moy),
            "price_med_fmt": _fmt(p_med),
            "price_avg_fmt": _fmt(p_moy),
        })
    except Exception as e:
        return JsonResponse({
            "total": 0, "sources": 5, "cities": 0,
            "price_med": 0, "price_avg": 0,
            "price_med_fmt": "—", "price_avg_fmt": "—",
        })
