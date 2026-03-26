"""
ImmoPredict SN — chart_views.py
Dashboard et Analytics avec données réelles.
"""
import json, logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse as _JsonResponse

logger = logging.getLogger(__name__)

PRICE_MIN = 10_000
PRICE_MAX = 2_000_000_000

C = {
    "gold":"#C9A84C","navy":"#0F2444","green":"#0E6B4A",
    "blue":"#2563EB","red":"#C0392B","purple":"#7C3AED",
    "teal":"#0891B2","muted":"#6B7280","white":"#FFFFFF",
    "border":"#DDE1EE","dark":"#111827",
    "src":{
        "coinafrique":"#F59E0B","expat_dakar":"#2563EB",
        "loger_dakar":"#0E6B4A","dakarvente":"#C0392B",
    },
}
PAL = [C["gold"],C["blue"],C["green"],C["red"],C["purple"],C["teal"],"#F59E0B","#16A085"]
KW_LOC = ["louer","location","locat","bail","mensuel","loyer"]
KW_VTE = ["vendre","vente","achat","cession"]


def _txn(row):
    # Vérifier property_type brut pour dakarvente
    pt = str(row.get("property_type") or "").lower()
    if any(k in pt for k in ["louer","location","locat"]): return "Location"
    t = str(row.get("statut") or row.get("transaction") or "").lower()
    if any(k in t for k in ["vente","vendre","cession"]): return "Vente"
    if any(k in t for k in ["locat","louer","bail","mensuel"]): return "Location"
    txt = str(row.get("title") or "").lower()
    if any(k in txt for k in KW_LOC): return "Location"
    if any(k in txt for k in KW_VTE): return "Vente"
    price = row.get("price", 0) or 0
    if 10_000 <= price <= 2_000_000: return "Location"
    return "Vente"


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
        BASE = ["id","price","surface_area","bedrooms","city","property_type"]
        dfs = []
        for model, src in SRCS:
            try:
                avail  = [f.name for f in model._meta.get_fields()]
                fields = [f for f in BASE if f in avail]
                rows = list(model.objects.values(*fields)[:max_per_source])
                if not rows: continue
                df = pd.DataFrame(rows)
                df["source"] = src
                dfs.append(df)
            except Exception as e:
                logger.error(f"Erreur source {src}: {e}")
                continue
        if not dfs: return _demo()
        df = pd.concat(dfs, ignore_index=True)
        df["price"]        = pd.to_numeric(df["price"], errors="coerce")
        df["surface_area"] = pd.to_numeric(df.get("surface_area", pd.Series(dtype=float)), errors="coerce")
        df["bedrooms"]     = pd.to_numeric(df.get("bedrooms", pd.Series(dtype=float)), errors="coerce")
        df["city"]         = (df["city"].fillna("Inconnu").astype(str)
                              .str.split(",").str[0].str.strip().str.title())

        # Nettoyer property_type — retirer les adresses et valeurs aberrantes
        VALID_TYPES = {
            "villa": "Villa",
            "appartement": "Appartement",
            "terrain": "Terrain",
            "duplex": "Duplex",
            "studio": "Studio",
            "maison": "Maison",
            "bureau": "Bureau",
            "local": "Local",
            "chambre": "Chambre",
            "immeuble": "Immeuble",
        }
        def clean_ptype(val):
            if not val or pd.isna(val): return "Autre"
            v = str(val).lower().strip()
            # Retirer les adresses (contiennent virgule + Sénégal ou Dakar)
            if "sénégal" in v or "senegal" in v or "dakar" in v: return "Autre"
            # Détecter le type réel
            for key, label in VALID_TYPES.items():
                if key in v: return label
            # Si trop long (adresse), retourner Autre
            if len(v) > 30: return "Autre"
            return str(val).strip().title()

        df["property_type"] = df["property_type"].apply(clean_ptype)

        # Corriger transaction pour dakarvente :
        # property_type "Appartements  À Louer" → Location
        def fix_txn(row):
            pt = str(row.get("property_type_raw","") or "").lower()
            if "louer" in pt or "location" in pt: return "Location"
            return row.get("transaction", "Vente")

        df = df[df["price"].notna() & (df["price"] > 0)].copy()
        if len(df) > 10:
            p_low  = df["price"].quantile(0.02)
            p_high = df["price"].quantile(0.99)
            df = df[df["price"].between(p_low, p_high)].copy()
        df["transaction"] = df.apply(_txn, axis=1)
        df["prix_m2"]     = df.apply(
            lambda r: r["price"]/r["surface_area"]
            if pd.notna(r.get("surface_area")) and r["surface_area"] > 10 else None, axis=1)
        logger.info(f"_load_data: {len(df)} annonces valides")
        return df
    except Exception as e:
        logger.error(f"_load_data erreur: {e}")
        return _demo()


def _demo():
    rng = np.random.default_rng(42)
    cities  = ["Dakar","Almadies","Ngor","Ouakam","Mermoz","Pikine","Fann","Yoff","Plateau","Sicap"]
    types   = ["Villa","Appartement","Terrain","Duplex","Studio","Maison"]
    sources = ["coinafrique","expat_dakar","loger_dakar","dakarvente"]
    n = 2000
    df = pd.DataFrame({
        "price":         np.clip(rng.lognormal(17.8,1.2,n), 500_000, 2_000_000_000),
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


def _gl():
    return dict(
        paper_bgcolor=C["white"], plot_bgcolor=C["white"],
        font=dict(family="Inter,sans-serif", color=C["dark"], size=12),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(gridcolor=C["border"], linecolor=C["border"], zeroline=False),
        yaxis=dict(gridcolor=C["border"], linecolor=C["border"], zeroline=False),
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
    )


def _fig_json(fig):
    fig.update_layout(**_gl())
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def _empty(msg="Données insuffisantes"):
    f = go.Figure()
    f.add_annotation(text=msg, showarrow=False,
                     font=dict(size=13, color=C["muted"]),
                     x=0.5, y=0.5, xref="paper", yref="paper")
    f.update_layout(**_gl())
    return f


def _ctx(request):
    from immoanalytics_dash.views import get_user_role
    return {"user": request.user, "role": get_user_role(request.user)}


@login_required(login_url='/immo/login/')
def dashboard_page(request):
    txn_f = request.GET.get("txn", "all")
    src_f = request.GET.get("src", "all")
    df_full = _load_data()
    sources = sorted(df_full["source"].unique().tolist())
    df = df_full.copy()
    if txn_f != "all": df = df[df["transaction"] == txn_f]
    if src_f != "all": df = df[df["source"]      == src_f]
    dv = df[df["transaction"] == "Vente"]
    dl = df[df["transaction"] == "Location"]
    total = len(df); nv = len(dv); nl = len(dl)
    pmed  = float(dv["price"].median()) if nv > 0 else 0
    pmoy  = float(dv["price"].mean())   if nv > 0 else 0
    nvilla= len(df[df["property_type"].str.lower().str.contains("villa", na=False)])
    kpis = [
        {"label":"Annonces totales",  "value":f"{total:,}",               "color":C["navy"],   "icon":"fas fa-database",   "sub":f"{nv} ventes · {nl} locations"},
        {"label":"Prix médian vente", "value":_fmt(pmed) if pmed else "—", "color":C["gold"],   "icon":"fas fa-tag",        "sub":"Valeur centrale"},
        {"label":"Prix moyen vente",  "value":_fmt(pmoy) if pmoy else "—", "color":C["green"],  "icon":"fas fa-chart-line", "sub":"Moyenne"},
        {"label":"Sources actives",   "value":str(df["source"].nunique()), "color":C["blue"],   "icon":"fas fa-layer-group","sub":"Plateformes"},
        {"label":"Villas",            "value":f"{nvilla:,}",               "color":C["purple"], "icon":"fas fa-home",       "sub":"Type villa"},
        {"label":"Villes couvertes",  "value":str(df["city"].nunique()),   "color":C["teal"],   "icon":"fas fa-map-pin",    "sub":"Quartiers"},
    ]
    # Distribution prix
    if nv > 5:
        dp = dv[(dv["price"] >= 500_000) & (dv["price"] <= 1_000_000_000)]
        fig_dist = go.Figure(go.Histogram(
            x=dp["price"]/1e6, nbinsx=50,
            marker_color=C["gold"], marker_line_width=0,
            hovertemplate="Tranche: %{x:.0f}M FCFA<br>Annonces: %{y}<extra></extra>",
        ))
        fig_dist.update_xaxes(title_text="Prix (M FCFA)")
        fig_dist.update_yaxes(title_text="Annonces")
    else:
        fig_dist = _empty("Aucune donnée de vente")
    # Répartition par source — VRAIES PROPORTIONS
    sc = df_full["source"].value_counts().reset_index()
    sc.columns = ["s","c"]
    colors_src = [C["src"].get(s, "#999") for s in sc["s"]]
    fig_pie = go.Figure(go.Pie(
        labels=sc["s"].str.replace("_"," ").str.title(),
        values=sc["c"], hole=.5,
        marker_colors=colors_src,
        textinfo="label+percent",
        hovertemplate="%{label}<br><b>%{value:,}</b> annonces (%{percent})<extra></extra>",
    ))
    fig_pie.update_layout(showlegend=True, margin=dict(l=10,r=10,t=20,b=10),
                          legend=dict(orientation="h", y=-0.1))
    # Top quartiers
    top_q = (dv[dv["price"] >= 500_000].groupby("city")["price"]
               .agg(["median","count"]).query("count >= 3")
               .sort_values("median", ascending=True).tail(12).reset_index())
    if len(top_q) > 0:
        fig_cities = go.Figure(go.Bar(
            x=top_q["median"]/1e6, y=top_q["city"], orientation="h",
            marker=dict(color=top_q["median"]/1e6, colorscale=[[0,"#E8EAF0"],[1,C["gold"]]], showscale=False),
            text=[f"{v:.0f}M" for v in top_q["median"]/1e6], textposition="outside",
            hovertemplate="%{y}<br><b>%{x:.1f}M</b> · %{customdata} ann.<extra></extra>",
            customdata=top_q["count"],
        ))
        fig_cities.update_xaxes(title_text="Prix médian (M FCFA)")
        fig_cities.update_layout(margin=dict(l=10,r=70,t=15,b=30))
    else:
        fig_cities = _empty()
    # Types de biens
    tc = df["property_type"].value_counts().head(8).reset_index(); tc.columns=["t","c"]
    if len(tc) > 0:
        fig_types = go.Figure(go.Bar(
            x=tc["t"], y=tc["c"], marker_color=PAL[:len(tc)],
            text=tc["c"], textposition="outside",
        ))
        fig_types.update_xaxes(tickangle=-25)
        fig_types.update_yaxes(title_text="Annonces")
    else:
        fig_types = _empty()
    # Vente vs Location par source
    txn_src = df.groupby(["source","transaction"]).size().reset_index(name="count")
    fig_trend = go.Figure()
    for txn, color in [("Vente",C["gold"]),("Location",C["blue"])]:
        sub = txn_src[txn_src["transaction"]==txn]
        if len(sub) > 0:
            fig_trend.add_trace(go.Bar(
                name=txn, x=sub["source"].str.replace("_"," ").str.title(),
                y=sub["count"], marker_color=color,
                text=sub["count"], textposition="outside",
            ))
    fig_trend.update_layout(barmode="group", legend=dict(orientation="h", y=-0.2))
    fig_trend.update_yaxes(title_text="Annonces")
    recent = df.nlargest(12,"price").to_dict("records")
    for r in recent:
        r["price_fmt"] = _fmt(r.get("price",0))
        r["src_color"] = C["src"].get(r.get("source",""), C["muted"])
        r["txn_color"] = C["green"] if r.get("transaction")=="Vente" else C["blue"]
        r["title_sh"]  = str(r.get("title","") or r.get("city",""))[:48]
        r["city"]      = str(r.get("city","") or "—")
        r["prop_type"] = str(r.get("property_type","") or "—")
    ctx = _ctx(request)
    ctx.update({
        "page_title":"Dashboard","kpis":kpis,
        "fig_dist":_fig_json(fig_dist),"fig_pie":_fig_json(fig_pie),
        "fig_cities":_fig_json(fig_cities),"fig_types":_fig_json(fig_types),
        "fig_trend":_fig_json(fig_trend),"recent":recent,"sources":sources,
        "txn_filter":txn_f,"src_filter":src_f,"total":total,"nv":nv,"nl":nl,
        "headers":["Bien","Prix","Ville","Type","Source","Transaction"],
    })
    return render(request, "immoanalytics/dashboard.html", ctx)


@login_required(login_url='/immo/login/')
def analytics_page(request):
    txn_f = request.GET.get("txn","all"); src_f = request.GET.get("src","all")
    type_f = request.GET.get("type","all"); city_f = request.GET.get("city","")
    df_full = _load_data()
    sources = sorted(df_full["source"].unique().tolist())
    types   = sorted(df_full["property_type"].dropna().unique().tolist())
    cities  = sorted(df_full["city"].dropna().unique().tolist())
    df = df_full.copy()
    if txn_f != "all": df = df[df["transaction"]==txn_f]
    if src_f != "all": df = df[df["source"]==src_f]
    if type_f!= "all": df = df[df["property_type"]==type_f]
    if city_f:         df = df[df["city"]==city_f]
    # Box plot
    top5 = df["property_type"].value_counts().head(5).index.tolist()
    fig_box = go.Figure()
    for i,t in enumerate(top5):
        sub = df[df["property_type"]==t]["price"]
        if len(sub) >= 3:
            fig_box.add_trace(go.Box(y=sub/1e6, name=t, marker_color=PAL[i%len(PAL)],
                                     boxmean=True, boxpoints=False))
    if not fig_box.data: fig_box = _empty()
    else:
        fig_box.update_yaxes(title_text="Prix (M FCFA)")
        fig_box.update_layout(showlegend=False)
    # Scatter
    dfs = df[df["surface_area"].between(15,3000) & df["price"].notna()].copy()
    if len(dfs) > 5:
        dfs["prix_M"] = dfs["price"]/1e6
        fig_sc = px.scatter(dfs.head(800), x="surface_area", y="prix_M",
                            color="property_type", color_discrete_sequence=PAL,
                            labels={"surface_area":"Superficie (m²)","prix_M":"Prix (M FCFA)"},
                            opacity=0.55)
        fig_sc.update_traces(marker_size=4)
    else:
        fig_sc = _empty("Surface non renseignée")
    # Bar villes
    cs = (df[df["price"]>=500_000].groupby("city")["price"]
            .agg(["median","count"]).query("count >= 3")
            .sort_values("median",ascending=True).tail(15).reset_index())
    if len(cs) > 0:
        fig_bar = go.Figure(go.Bar(
            x=cs["median"]/1e6, y=cs["city"], orientation="h",
            marker=dict(color=cs["median"]/1e6, colorscale=[[0,"#EEF0F8"],[1,C["gold"]]], showscale=False),
            text=[f"{v:.0f}M" for v in cs["median"]/1e6], textposition="outside",
            hovertemplate="%{y}<br>Médiane: <b>%{x:.1f}M</b><extra></extra>",
        ))
        fig_bar.update_xaxes(title_text="Prix médian (M FCFA)")
        fig_bar.update_layout(margin=dict(l=10,r=70,t=15,b=30))
    else:
        fig_bar = _empty()
    # Sources
    ss = df.groupby("source")["price"].agg(["median","mean","count"]).reset_index()
    ss = ss[ss["count"]>=3]
    if len(ss) > 0:
        lbl = ss["source"].str.replace("_"," ").str.title()
        fig_src = go.Figure()
        fig_src.add_trace(go.Bar(name="Médiane",x=lbl,y=ss["median"]/1e6,marker_color=C["gold"],
                                  text=[f"{v:.0f}M" for v in ss["median"]/1e6],textposition="outside"))
        fig_src.add_trace(go.Bar(name="Moyenne",x=lbl,y=ss["mean"]/1e6,marker_color=C["blue"],
                                  text=[f"{v:.0f}M" for v in ss["mean"]/1e6],textposition="outside"))
        fig_src.update_layout(barmode="group",legend=dict(orientation="h",y=-0.2))
        fig_src.update_yaxes(title_text="Prix (M FCFA)")
    else:
        fig_src = _empty()
    # Prix/m²
    dm2 = df[df["prix_m2"].notna() & df["prix_m2"].between(10_000,5_000_000)].copy() if "prix_m2" in df.columns else pd.DataFrame()
    if len(dm2) > 5:
        fig_m2 = go.Figure(go.Histogram(x=dm2["prix_m2"]/1e3, nbinsx=40,
                                         marker_color=C["green"],marker_line_width=0))
        fig_m2.update_xaxes(title_text="Prix au m² (K FCFA)")
        fig_m2.update_yaxes(title_text="Annonces")
    else:
        fig_m2 = _empty("Surface non renseignée")
    # Chambres
    dbc = df[df["bedrooms"].between(1,8) & df["price"].notna()].copy()
    if len(dbc) > 5:
        bs = dbc.groupby("bedrooms")["price"].agg(["median","count"]).reset_index().query("count>=3")
        if len(bs) > 0:
            fig_beds = go.Figure(go.Bar(
                x=[f"{int(b)} ch." for b in bs["bedrooms"]], y=bs["median"]/1e6,
                marker_color=PAL[:len(bs)],
                text=[f"{v:.0f}M" for v in bs["median"]/1e6], textposition="outside",
            ))
            fig_beds.update_yaxes(title_text="Prix médian (M FCFA)")
        else: fig_beds = _empty()
    else: fig_beds = _empty()
    stats_data = []
    if len(df) > 0:
        s = df["price"].describe()
        stats_data = [("Annonces",f"{int(s.get('count',0)):,}"),
                      ("Prix minimum",_fmt(s.get("min",0))),("1er quartile",_fmt(s.get("25%",0))),
                      ("Médiane",_fmt(s.get("50%",0))),("Moyenne",_fmt(s.get("mean",0))),
                      ("3e quartile",_fmt(s.get("75%",0))),("Prix maximum",_fmt(s.get("max",0))),
                      ("Écart-type",_fmt(s.get("std",0)))]
    ctx = _ctx(request)
    ctx.update({"page_title":"Analytics","fig_box":_fig_json(fig_box),"fig_sc":_fig_json(fig_sc),
                "fig_bar":_fig_json(fig_bar),"fig_src":_fig_json(fig_src),
                "fig_m2":_fig_json(fig_m2),"fig_beds":_fig_json(fig_beds),
                "stats":stats_data,"sources":sources,"types":types,"cities":cities,
                "txn_filter":txn_f,"src_filter":src_f,"type_filter":type_f,"city_filter":city_f})
    return render(request, "immoanalytics/analytics.html", ctx)


def api_stats_real(request):
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty)
        import statistics as _stats
        models_map = {"coinafrique":CoinAfriqueProperty,"expat_dakar":ExpatDakarProperty,
                      "loger_dakar":LogerDakarProperty,"dakarvente":DakarVenteProperty}
        total=0; all_prices=[]; cities_set=set()
        for src,model in models_map.items():
            try:
                total += model.objects.count()
                for p in model.objects.filter(price__isnull=False,price__gt=0).values_list("price",flat=True)[:1000]:
                    if p: all_prices.append(float(p))
                for c in model.objects.values_list("city",flat=True).distinct()[:20]:
                    if c and c.strip(): cities_set.add(c.strip().split(",")[0].strip().title())
            except: pass
        p_med = _stats.median(all_prices) if all_prices else 0
        p_moy = _stats.mean(all_prices)   if all_prices else 0
        return _JsonResponse({"total":total,"sources":len(models_map),"cities":len(cities_set),
                               "price_med":round(p_med),"price_avg":round(p_moy),
                               "price_med_fmt":_fmt(p_med),"price_avg_fmt":_fmt(p_moy)})
    except Exception as e:
        return _JsonResponse({"total":0,"sources":4,"cities":0,"price_med":0,"price_avg":0,
                               "price_med_fmt":"—","price_avg_fmt":"—"})


def api_debug_db(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return _JsonResponse({"error":"Admin seulement"},status=403)
    from properties.models import (CoinAfriqueProperty,ExpatDakarProperty,
        LogerDakarProperty,DakarVenteProperty)
    result={"sources":{},"tables_manquantes":[],"_load_data_count":0}
    for name,model in [("coinafrique",CoinAfriqueProperty),("expat_dakar",ExpatDakarProperty),
                        ("loger_dakar",LogerDakarProperty),("dakarvente",DakarVenteProperty)]:
        try:
            total=model.objects.count()
            with_price=model.objects.filter(price__isnull=False).count()
            sample=list(model.objects.filter(price__isnull=False).values_list("price",flat=True)[:5])
            result["sources"][name]={"status":"OK","total":total,"with_price":with_price,
                                      "sample_prices":[float(p) for p in sample if p]}
        except Exception as e:
            result["sources"][name]={"status":"TABLE MANQUANTE","detail":str(e).split("\n")[0]}
            result["tables_manquantes"].append(name)
    try:
        df=_load_data()
        result["_load_data_count"]=len(df)
        if len(df)>0: result["_load_data_sources"]=df["source"].value_counts().to_dict()
    except Exception as e:
        result["_load_data_error"]=str(e)
    return _JsonResponse(result,json_dumps_params={"indent":2})