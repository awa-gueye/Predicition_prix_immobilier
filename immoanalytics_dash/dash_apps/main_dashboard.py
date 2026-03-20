"""
Dashboard principal — DjangoDash("MainDashboard")
Sans emojis · Design professionnel · Tous graphes fonctionnels
"""
import logging
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)

app = DjangoDash(
    name="MainDashboard",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    add_bootstrap_links=False,
)

C = {
    "gold":"#B8955A","dark":"#1A1A2E","green":"#1A5C3A","blue":"#2563EB",
    "red":"#C0392B","purple":"#7C3AED","muted":"#8B8680",
    "bg":"#F4F5F7","white":"#FFFFFF","border":"#E8EAF0",
    "src":{"coinafrique":"#F39C12","expat_dakar":"#2563EB",
           "loger_dakar":"#1A5C3A","dakarvente":"#C0392B","immosenegal":"#7C3AED"},
}
PRICE_MIN = 1_000_000
KW_LOC = ["louer","location","locat","bail","mensuel"]
KW_VTE = ["vendre","vente","achat","cession"]


def _txn(row):
    t = str(row.get("statut") or row.get("transaction") or "").lower()
    if any(k in t for k in ["vente","vendre"]): return "Vente"
    if any(k in t for k in ["locat","louer"]):  return "Location"
    for fld in ["title"]:
        txt = str(row.get(fld) or "").lower()
        if any(k in txt for k in KW_LOC): return "Location"
        if any(k in txt for k in KW_VTE): return "Vente"
    return "Autre"


def _load():
    try:
        from properties.models import (CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty, ImmoSenegalProperty)
        SRCS = [(CoinAfriqueProperty,"coinafrique",["latitude","longitude"]),
                (ExpatDakarProperty, "expat_dakar",[]),
                (LogerDakarProperty, "loger_dakar",[]),
                (DakarVenteProperty, "dakarvente", ["latitude","longitude"]),
                (ImmoSenegalProperty,"immosenegal",["transaction","garage"])]
        BASE = ["id","price","surface_area","bedrooms","bathrooms",
                "city","property_type","statut","title","scraped_at"]
        dfs = []
        for model, src, extra in SRCS:
            avail  = [f.name for f in model._meta.get_fields()]
            fields = [f for f in BASE+extra if f in avail]
            rows   = list(model.objects.filter(
                price__gte=PRICE_MIN, price__lte=5_000_000_000
            ).values(*fields)[:2000])
            if not rows: continue
            df = pd.DataFrame(rows); df["source"] = src; dfs.append(df)
        if not dfs: return _demo()
        df = pd.concat(dfs, ignore_index=True)
        df["price"]        = pd.to_numeric(df["price"], errors="coerce")
        df["surface_area"] = pd.to_numeric(df["surface_area"], errors="coerce")
        df["city"]         = (df["city"].fillna("Inconnu").astype(str)
                              .str.split(",").str[0].str.strip().str.title())
        df["property_type"]= df["property_type"].fillna("Autre").astype(str).str.strip()
        df = df[df["price"].notna() & (df["price"] >= PRICE_MIN)].copy()
        df["transaction"]  = df.apply(_txn, axis=1)
        df["prix_m2"]      = df.apply(
            lambda r: r["price"]/r["surface_area"]
            if pd.notna(r.get("surface_area")) and r["surface_area"]>0 else None, axis=1)
        return df
    except Exception as e:
        logger.warning(f"DB: {e}"); return _demo()


def _demo():
    rng = np.random.default_rng(42)
    cities=["Dakar","Almadies","Ngor","Ouakam","Mermoz","Pikine","Fann","Yoff","Plateau","Sicap"]
    types=["Villa","Appartement","Terrain","Duplex","Studio"]
    sources=["coinafrique","expat_dakar","loger_dakar","dakarvente","immosenegal"]
    n=500
    df=pd.DataFrame({"price":np.clip(rng.lognormal(17.5,1.1,n),2e6,8e8),
        "surface_area":np.clip(rng.lognormal(4.5,.8,n),20,2000),
        "bedrooms":rng.integers(1,8,n).astype(float),
        "city":rng.choice(cities,n),"property_type":rng.choice(types,n),
        "source":rng.choice(sources,n),
        "transaction":rng.choice(["Vente","Location"],n,p=[.6,.4]),
        "title":["Annonce"]*n})
    df["prix_m2"]=df["price"]/df["surface_area"]; return df


def _fmt(p):
    if not p or p<PRICE_MIN: return "—"
    if p>=1e9: return f"{p/1e9:.2f} Mds"
    if p>=1e6: return f"{p/1e6:.1f}M"
    if p>=1e3: return f"{p/1e3:.0f}K"
    return f"{p:,.0f}"


def _gl(t=""):
    base = {"paper_bgcolor":C["white"],"plot_bgcolor":C["white"],
            "font":{"family":"Inter,sans-serif","color":C["dark"],"size":12},
            "margin":{"l":12,"r":12,"t":32 if t else 12,"b":12},
            "xaxis":{"gridcolor":C["border"],"linecolor":C["border"],"zeroline":False},
            "yaxis":{"gridcolor":C["border"],"linecolor":C["border"],"zeroline":False},
            "legend":{"font":{"size":11},"bgcolor":"transparent"}}
    if t: base["title"]={"text":t,"font":{"size":12,"color":C["muted"]},"x":0.01,"xanchor":"left"}
    return base


def _kpi(label, value, color, icon):
    return html.Div([
        html.Div(html.I(className=icon, style={"fontSize":".88rem","color":color}),
                 style={"width":"38px","height":"38px","borderRadius":"9px",
                        "background":f"{color}15","display":"flex",
                        "alignItems":"center","justifyContent":"center","flexShrink":"0"}),
        html.Div([
            html.Div(value, style={"fontFamily":"Playfair Display,serif",
                                    "fontSize":"1.5rem","fontWeight":"700",
                                    "color":C["dark"],"lineHeight":"1"}),
            html.Div(label, style={"fontSize":".7rem","color":C["muted"],
                                   "marginTop":".15rem","textTransform":"uppercase",
                                   "letterSpacing":".06em"}),
        ]),
    ], style={"background":C["white"],"borderRadius":"10px","padding":"1rem 1.1rem",
              "border":f"1px solid {C['border']}","borderLeft":f"4px solid {color}",
              "display":"flex","alignItems":"center","gap":".8rem",
              "boxShadow":"0 1px 4px rgba(0,0,0,.05)"})


def _card(header, child_id, h=280):
    return html.Div([
        html.Div(header, style={"padding":".65rem 1rem","borderBottom":f"1px solid {C['border']}",
                                 "fontWeight":"600","fontSize":".82rem","color":C["dark"]}),
        dcc.Graph(id=child_id, config={"displayModeBar":False},
                  style={"height":f"{h}px"}),
    ], style={"background":C["white"],"borderRadius":"10px","border":f"1px solid {C['border']}",
              "boxShadow":"0 1px 4px rgba(0,0,0,.05)","overflow":"hidden"})


# ── Layout ─────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Interval(id="md-iv", interval=600_000, n_intervals=0),

    # Filtres
    html.Div([
        html.Div([
            html.Label("Transaction", style={"fontSize":".67rem","textTransform":"uppercase",
                       "letterSpacing":".08em","color":C["muted"],"display":"block","marginBottom":".25rem",
                       "fontFamily":"JetBrains Mono,monospace"}),
            dcc.Dropdown(id="md-txn",
                options=[{"label":"Toutes","value":"all"},{"label":"Vente","value":"Vente"},
                         {"label":"Location","value":"Location"}],
                value="all", clearable=False,
                style={"width":"160px","fontFamily":"Inter,sans-serif","fontSize":".82rem"}),
        ]),
        html.Div([
            html.Label("Source", style={"fontSize":".67rem","textTransform":"uppercase",
                       "letterSpacing":".08em","color":C["muted"],"display":"block","marginBottom":".25rem",
                       "fontFamily":"JetBrains Mono,monospace"}),
            dcc.Dropdown(id="md-src",
                options=[{"label":"Toutes sources","value":"all"}],
                value="all", clearable=False,
                style={"width":"195px","fontFamily":"Inter,sans-serif","fontSize":".82rem"}),
        ]),
    ], style={"display":"flex","gap":"1.5rem","alignItems":"flex-end",
              "marginBottom":"1.2rem","flexWrap":"wrap"}),

    # KPIs
    html.Div(id="md-kpis", style={"display":"grid",
        "gridTemplateColumns":"repeat(auto-fill,minmax(175px,1fr))",
        "gap":"1rem","marginBottom":"1.2rem"}),

    # Ligne 1
    html.Div([
        html.Div(_card("Distribution des prix — Vente", "md-dist", 270),
                 style={"flex":"1.5","minWidth":"280px"}),
        html.Div(_card("Annonces par source", "md-pie", 270),
                 style={"flex":"1","minWidth":"230px"}),
    ], style={"display":"flex","gap":"1rem","marginBottom":"1rem","flexWrap":"wrap"}),

    # Ligne 2
    html.Div([
        html.Div(_card("Top quartiers — Prix médian", "md-cities", 300),
                 style={"flex":"1","minWidth":"280px"}),
        html.Div(_card("Répartition par type de bien", "md-types", 300),
                 style={"flex":"1","minWidth":"280px"}),
    ], style={"display":"flex","gap":"1rem","marginBottom":"1rem","flexWrap":"wrap"}),

    # Tableau
    html.Div([
        html.Div("Annonces — prix les plus élevés",
                 style={"padding":".65rem 1rem","borderBottom":f"1px solid {C['border']}",
                        "fontWeight":"600","fontSize":".82rem","color":C["dark"]}),
        html.Div(id="md-table", style={"overflowX":"auto"}),
    ], style={"background":C["white"],"borderRadius":"10px","border":f"1px solid {C['border']}",
              "boxShadow":"0 1px 4px rgba(0,0,0,.05)","overflow":"hidden"}),

], style={"padding":"1.2rem","background":C["bg"],"minHeight":"100%","fontFamily":"Inter,sans-serif"})


@app.callback(Output("md-src","options"), Input("md-iv","n_intervals"))
def load_srcs(_):
    df = _load()
    return [{"label":"Toutes sources","value":"all"}] + [
        {"label":s.replace("_"," ").title(),"value":s}
        for s in sorted(df["source"].unique())]


@app.callback(
    [Output("md-kpis","children"), Output("md-dist","figure"),
     Output("md-pie","figure"),    Output("md-cities","figure"),
     Output("md-types","figure"),  Output("md-table","children")],
    [Input("md-txn","value"), Input("md-src","value"), Input("md-iv","n_intervals")],
)
def update(txn, src, _):
    df = _load()
    if txn != "all": df = df[df["transaction"] == txn]
    if src != "all": df = df[df["source"]      == src]
    dv = df[df["transaction"] == "Vente"]
    total = len(df); nv = len(dv)
    pmed = float(dv["price"].median()) if nv>0 else 0
    pmoy = float(dv["price"].mean())   if nv>0 else 0

    kpis = [
        _kpi("Annonces totales",  f"{total:,}",                          C["blue"],   "fas fa-database"),
        _kpi("Prix médian vente", f"{_fmt(pmed)} FCFA" if pmed else "—", C["gold"],   "fas fa-tag"),
        _kpi("Prix moyen vente",  f"{_fmt(pmoy)} FCFA" if pmoy else "—", C["green"],  "fas fa-chart-line"),
        _kpi("Sources actives",   str(df["source"].nunique()),            C["purple"], "fas fa-layer-group"),
    ]

    # Distribution
    if nv > 10:
        dp = dv[dv["price"].between(dv["price"].quantile(.02), dv["price"].quantile(.98))]
    else:
        dp = dv
    if len(dp) > 0:
        fig_d = px.histogram(dp, x="price", nbins=40,
                             color_discrete_sequence=[C["gold"]],
                             labels={"price":"Prix (FCFA)","count":"Annonces"})
        fig_d.update_traces(marker_line_width=0)
        fig_d.update_xaxes(tickformat=".2s")
        fig_d.update_yaxes(title_text="Annonces")
    else:
        fig_d = go.Figure()
        fig_d.add_annotation(text="Aucune donnée", showarrow=False, font={"color":C["muted"]})
    fig_d.update_layout(**_gl())

    # Donut sources
    sc = df["source"].value_counts().reset_index(); sc.columns=["s","c"]
    colors = [C["src"].get(s,"#BDC3C7") for s in sc["s"]]
    fig_p = go.Figure(go.Pie(
        labels=sc["s"].str.replace("_"," ").str.title(),
        values=sc["c"], hole=.55,
        marker_colors=colors,
        textinfo="percent+label", textfont={"size":11},
        hovertemplate="%{label}<br><b>%{value}</b> annonces (%{percent})<extra></extra>",
    ))
    fig_p.update_layout(**_gl()); fig_p.update_layout(showlegend=False)

    # Top quartiers
    top = (dv.groupby("city")["price"].agg(["median","count"])
           .query("count >= 3").sort_values("median", ascending=True).tail(10).reset_index())
    if len(top) > 0:
        fig_c = go.Figure(go.Bar(
            x=top["median"]/1e6, y=top["city"], orientation="h",
            marker=dict(color=top["median"]/1e6,
                        colorscale=[[0,"#E8EAF0"],[.5,C["gold"]+"80"],[1,C["gold"]]],
                        showscale=False),
            text=[f"{v:.0f}M" for v in top["median"]/1e6],
            textposition="outside",
            hovertemplate="%{y}<br><b>%{x:.1f}M FCFA</b><br>%{customdata} annonces<extra></extra>",
            customdata=top["count"],
        ))
        fig_c.update_xaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
        fig_c.update_yaxes(tickfont={"size":11})
    else:
        fig_c = go.Figure()
        fig_c.add_annotation(text="Données insuffisantes", showarrow=False, font={"color":C["muted"]})
    fig_c.update_layout(**_gl())

    # Types
    tc = df["property_type"].value_counts().head(7).reset_index(); tc.columns=["t","c"]
    pal = [C["gold"],C["blue"],C["green"],C["red"],C["purple"],"#F39C12","#16A085"]
    if len(tc) > 0:
        fig_t = go.Figure(go.Bar(
            x=tc["t"], y=tc["c"],
            marker_color=pal[:len(tc)],
            text=tc["c"], textposition="outside",
            hovertemplate="%{x}<br><b>%{y}</b> annonces<extra></extra>",
        ))
        fig_t.update_xaxes(tickangle=-25)
        fig_t.update_yaxes(title_text="Annonces")
    else:
        fig_t = go.Figure()
        fig_t.add_annotation(text="Données insuffisantes", showarrow=False, font={"color":C["muted"]})
    fig_t.update_layout(**_gl())

    # Tableau
    recent = df.nlargest(10, "price")
    TH = {"padding":".55rem .9rem","background":"#F7F8FA","fontSize":".7rem",
          "fontWeight":"600","color":C["muted"],"textTransform":"uppercase",
          "letterSpacing":".07em","borderBottom":f"1px solid {C['border']}","whiteSpace":"nowrap"}
    TD = {"padding":".6rem .9rem","fontSize":".81rem","color":C["dark"],
          "borderBottom":f"1px solid #F0F1F5"}
    rows = []
    for _, r in recent.iterrows():
        price = r.get("price",0) or 0
        txn_v = str(r.get("transaction","") or "")
        tc_   = C["green"] if txn_v=="Vente" else C["blue"]
        src_v = str(r.get("source","") or "")
        sc_   = C["src"].get(src_v, C["muted"])
        title_v = str(r.get("title","") or "")
        rows.append(html.Tr([
            html.Td(title_v[:45]+("…" if len(title_v)>45 else ""),
                    style={**TD,"maxWidth":"180px","overflow":"hidden","textOverflow":"ellipsis","whiteSpace":"nowrap"}),
            html.Td(f"{_fmt(price)} FCFA",
                    style={**TD,"fontWeight":"700","color":C["gold"],"whiteSpace":"nowrap"}),
            html.Td(str(r.get("city","—") or "—"), style=TD),
            html.Td(str(r.get("property_type","—") or "—"), style=TD),
            html.Td(html.Span(src_v.replace("_"," ").title(),
                              style={"background":f"{sc_}15","color":sc_,"padding":".12rem .45rem",
                                     "borderRadius":"4px","fontSize":".68rem","fontWeight":"600",
                                     "fontFamily":"JetBrains Mono,monospace"}), style=TD),
            html.Td(html.Span(txn_v or "—",
                              style={"background":f"{tc_}12","color":tc_,"padding":".12rem .4rem",
                                     "borderRadius":"4px","fontSize":".7rem","fontWeight":"600"}),
                    style=TD),
        ]))
    table = html.Table(
        [html.Thead(html.Tr([html.Th(h,style=TH) for h in
                             ["Titre","Prix","Ville","Type","Source","Transaction"]])),
         html.Tbody(rows)],
        style={"width":"100%","borderCollapse":"collapse"})
    return kpis, fig_d, fig_p, fig_c, fig_t, table


def register_main_dashboard():
    logger.info("MainDashboard enregistré."); return app
