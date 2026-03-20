"""
Dashboard Analytics — DjangoDash("AnalyticsDashboard")
Sans emojis · Tous graphes fonctionnels · Design professionnel
"""
import logging
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)

app = DjangoDash(
    name="AnalyticsDashboard",
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
PAL = [C["gold"],C["blue"],C["green"],C["red"],C["purple"],"#F39C12","#16A085","#2C3E50"]
PRICE_MIN = 1_000_000


def _load():
    from .main_dashboard import _load as _ld, _demo
    try:    return _ld()
    except: return _demo()


def _fmt(p):
    if not p or p<PRICE_MIN: return "—"
    if p>=1e9: return f"{p/1e9:.2f} Mds"
    if p>=1e6: return f"{p/1e6:.1f}M"
    return f"{p/1e3:.0f}K"


def _gl(margins=None):
    m = margins or {"l":12,"r":12,"t":12,"b":12}
    return {"paper_bgcolor":C["white"],"plot_bgcolor":C["white"],
            "font":{"family":"Inter,sans-serif","color":C["dark"],"size":12},
            "margin":m,
            "xaxis":{"gridcolor":C["border"],"linecolor":C["border"],"zeroline":False},
            "yaxis":{"gridcolor":C["border"],"linecolor":C["border"],"zeroline":False},
            "legend":{"font":{"size":11},"bgcolor":"transparent","orientation":"h","y":-0.15}}


def _card(header, child_id, h=280):
    return html.Div([
        html.Div(header, style={"padding":".65rem 1rem","borderBottom":f"1px solid {C['border']}",
                                 "fontWeight":"600","fontSize":".82rem","color":C["dark"]}),
        dcc.Graph(id=child_id, config={"displayModeBar":False}, style={"height":f"{h}px"}),
    ], style={"background":C["white"],"borderRadius":"10px","border":f"1px solid {C['border']}",
              "boxShadow":"0 1px 4px rgba(0,0,0,.05)","overflow":"hidden"})


def _label(text):
    return html.Label(text, style={"fontSize":".67rem","textTransform":"uppercase",
                                    "letterSpacing":".08em","color":C["muted"],
                                    "display":"block","marginBottom":".25rem",
                                    "fontFamily":"JetBrains Mono,monospace"})


# ── Layout ─────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Interval(id="an-iv", interval=600_000, n_intervals=0),

    # Filtres
    html.Div([
        html.Div([_label("Transaction"),
                  dcc.Dropdown(id="an-txn",
                      options=[{"label":"Vente + Location","value":"all"},
                               {"label":"Vente","value":"Vente"},
                               {"label":"Location","value":"Location"}],
                      value="Vente", clearable=False,
                      style={"width":"190px","fontFamily":"Inter,sans-serif","fontSize":".82rem"})]),
        html.Div([_label("Source"),
                  dcc.Dropdown(id="an-src", value="all", clearable=False,
                      style={"width":"190px","fontFamily":"Inter,sans-serif","fontSize":".82rem"})]),
        html.Div([_label("Type de bien"),
                  dcc.Dropdown(id="an-type", value="all", clearable=False,
                      style={"width":"185px","fontFamily":"Inter,sans-serif","fontSize":".82rem"})]),
        html.Div([_label("Ville"),
                  dcc.Dropdown(id="an-city", clearable=True, placeholder="Toutes",
                      style={"width":"165px","fontFamily":"Inter,sans-serif","fontSize":".82rem"})]),
    ], style={"display":"flex","gap":"1.2rem","alignItems":"flex-end",
              "marginBottom":"1.2rem","flexWrap":"wrap",
              "background":C["white"],"padding":"1rem 1.2rem",
              "borderRadius":"10px","border":f"1px solid {C['border']}",
              "boxShadow":"0 1px 4px rgba(0,0,0,.05)"}),

    # Ligne 1 — Box plot + Scatter
    html.Div([
        html.Div(_card("Distribution des prix par type (box plot)", "an-box", 300),
                 style={"flex":"1","minWidth":"280px"}),
        html.Div(_card("Prix vs Superficie", "an-sc", 300),
                 style={"flex":"1","minWidth":"280px"}),
    ], style={"display":"flex","gap":"1rem","marginBottom":"1rem","flexWrap":"wrap"}),

    # Ligne 2 — Bar villes + Stats
    html.Div([
        html.Div(_card("Prix médian par ville (min. 3 annonces)", "an-bar", 320),
                 style={"flex":"1.4","minWidth":"300px"}),
        html.Div([
            html.Div("Statistiques descriptives",
                     style={"padding":".65rem 1rem","borderBottom":f"1px solid {C['border']}",
                            "fontWeight":"600","fontSize":".82rem","color":C["dark"]}),
            html.Div(id="an-stats", style={"padding":"1rem","overflowY":"auto","height":"260px"}),
        ], style={"background":C["white"],"borderRadius":"10px","border":f"1px solid {C['border']}",
                  "boxShadow":"0 1px 4px rgba(0,0,0,.05)","overflow":"hidden",
                  "flex":"1","minWidth":"220px"}),
    ], style={"display":"flex","gap":"1rem","marginBottom":"1rem","flexWrap":"wrap"}),

    # Ligne 3 — Sources + Prix m²
    html.Div([
        html.Div(_card("Comparaison sources — Prix médian vs moyen", "an-src-c", 280),
                 style={"flex":"1","minWidth":"280px"}),
        html.Div(_card("Distribution du prix au m²", "an-m2", 280),
                 style={"flex":"1","minWidth":"280px"}),
    ], style={"display":"flex","gap":"1rem","flexWrap":"wrap"}),

], style={"padding":"1.2rem","background":C["bg"],"minHeight":"100%","fontFamily":"Inter,sans-serif"})


@app.callback(
    [Output("an-src","options"), Output("an-type","options"), Output("an-city","options")],
    Input("an-iv","n_intervals"),
)
def load_opts(_):
    df = _load()
    so = [{"label":"Toutes sources","value":"all"}]+[
         {"label":s.replace("_"," ").title(),"value":s} for s in sorted(df["source"].unique())]
    to = [{"label":"Tous types","value":"all"}]+[
         {"label":t,"value":t} for t in sorted(df["property_type"].dropna().unique())]
    co = [{"label":c,"value":c} for c in sorted(df["city"].dropna().unique())]
    return so, to, co


@app.callback(
    [Output("an-box","figure"), Output("an-sc","figure"), Output("an-bar","figure"),
     Output("an-stats","children"), Output("an-src-c","figure"), Output("an-m2","figure")],
    [Input("an-txn","value"), Input("an-src","value"),
     Input("an-type","value"), Input("an-city","value"), Input("an-iv","n_intervals")],
)
def update(txn, src, pt, city, _):
    df = _load()
    if txn != "all":       df = df[df["transaction"]   == txn]
    if src != "all":       df = df[df["source"]         == src]
    if pt  and pt!="all":  df = df[df["property_type"] == pt]
    if city:               df = df[df["city"]           == city]

    empty = go.Figure()
    empty.add_annotation(text="Données insuffisantes", showarrow=False,
                         font={"color":C["muted"],"size":13})
    empty.update_layout(**_gl())

    if len(df) < 3:
        return empty, empty, empty, html.P("Aucune donnée.", style={"color":C["muted"]}), empty, empty

    # ── Box plot par type ─────────────────────────────────────────────────────
    top_types = df["property_type"].value_counts().head(5).index.tolist()
    df_box    = df[df["property_type"].isin(top_types)].copy()
    if len(df_box) > 0:
        fig_box = go.Figure()
        for i, t in enumerate(top_types):
            sub = df_box[df_box["property_type"] == t]["price"]
            if len(sub) > 0:
                fig_box.add_trace(go.Box(
                    y=sub, name=t, marker_color=PAL[i % len(PAL)],
                    boxmean=True, line_width=1.5,
                    hovertemplate=f"<b>{t}</b><br>%{{y:,.0f}} FCFA<extra></extra>",
                ))
        fig_box.update_yaxes(tickformat=".2s", title_text="Prix (FCFA)")
    else:
        fig_box = empty
    fig_box.update_layout(**_gl({"l":50,"r":12,"t":12,"b":40}), showlegend=False)

    # ── Scatter prix vs surface ───────────────────────────────────────────────
    dfs = df[df["surface_area"].between(15, 2000) & df["price"].notna()].head(400)
    if len(dfs) > 5:
        fig_sc = px.scatter(
            dfs, x="surface_area", y="price",
            color="property_type", color_discrete_sequence=PAL,
            labels={"surface_area":"Superficie (m²)","price":"Prix (FCFA)"},
            opacity=0.7,
        )
        fig_sc.update_traces(marker_size=6)
        fig_sc.update_yaxes(tickformat=".2s")
        fig_sc.update_xaxes(title_text="Superficie (m²)")
        fig_sc.update_yaxes(title_text="Prix (FCFA)")
    else:
        fig_sc = empty
    fig_sc.update_layout(**_gl({"l":50,"r":12,"t":12,"b":40}))

    # ── Bar villes ────────────────────────────────────────────────────────────
    cs = (df.groupby("city")["price"].agg(["median","count"])
          .query("count >= 3").sort_values("median", ascending=True).tail(12).reset_index())
    if len(cs) > 0:
        fig_bar = go.Figure(go.Bar(
            x=cs["median"]/1e6, y=cs["city"], orientation="h",
            marker=dict(color=cs["median"]/1e6,
                        colorscale=[[0,"#E8EAF0"],[.5,f"{C['gold']}80"],[1,C["gold"]]],
                        showscale=False),
            text=[f"{v:.0f}M" for v in cs["median"]/1e6], textposition="outside",
            hovertemplate="%{y}<br><b>%{x:.1f}M FCFA</b><br>%{customdata} ann.<extra></extra>",
            customdata=cs["count"],
        ))
        fig_bar.update_xaxes(title_text="Prix médian (M FCFA)", ticksuffix="M")
        fig_bar.update_yaxes(tickfont={"size":11})
    else:
        fig_bar = empty
    fig_bar.update_layout(**_gl({"l":10,"r":60,"t":12,"b":40}))

    # ── Stats ─────────────────────────────────────────────────────────────────
    s = df["price"].describe()
    items = [
        ("Nombre d'annonces",   f"{int(s['count']):,}"),
        ("Prix minimum",        f"{_fmt(s['min'])} FCFA"),
        ("1er quartile (Q25)",  f"{_fmt(s['25%'])} FCFA"),
        ("Médiane (Q50)",       f"{_fmt(s['50%'])} FCFA"),
        ("Moyenne",             f"{_fmt(s['mean'])} FCFA"),
        ("3e quartile (Q75)",   f"{_fmt(s['75%'])} FCFA"),
        ("Prix maximum",        f"{_fmt(s['max'])} FCFA"),
        ("Écart-type",          f"{_fmt(s['std'])} FCFA"),
    ]
    stats_rows = [
        html.Div([
            html.Span(k, style={"fontSize":".75rem","color":C["muted"],"flex":"1"}),
            html.Span(v, style={"fontSize":".78rem","fontWeight":"600","color":C["dark"]}),
        ], style={"display":"flex","justifyContent":"space-between","alignItems":"center",
                  "padding":".45rem 0","borderBottom":f"1px solid #F0F1F5"})
        for k, v in items
    ]
    stats_div = html.Div(stats_rows)

    # ── Comparaison sources ───────────────────────────────────────────────────
    ss = df.groupby("source")["price"].agg(["median","mean","count"]).reset_index()
    ss = ss[ss["count"] >= 3]
    if len(ss) > 0:
        fig_src = go.Figure()
        labels = ss["source"].str.replace("_"," ").str.title()
        fig_src.add_trace(go.Bar(
            name="Médiane", x=labels, y=ss["median"]/1e6,
            marker_color=C["gold"], text=[f"{v:.0f}M" for v in ss["median"]/1e6],
            textposition="outside",
        ))
        fig_src.add_trace(go.Bar(
            name="Moyenne", x=labels, y=ss["mean"]/1e6,
            marker_color=C["blue"], text=[f"{v:.0f}M" for v in ss["mean"]/1e6],
            textposition="outside",
        ))
        fig_src.update_layout(barmode="group")
        fig_src.update_yaxes(title_text="Prix (M FCFA)", ticksuffix="M")
    else:
        fig_src = empty
    fig_src.update_layout(**_gl({"l":50,"r":12,"t":12,"b":50}))

    # ── Prix au m² ────────────────────────────────────────────────────────────
    if "prix_m2" in df.columns:
        dm2 = df[df["prix_m2"].between(50_000, 5_000_000)].copy()
    else:
        dm2 = pd.DataFrame()
    if len(dm2) > 5:
        fig_m2 = px.histogram(
            dm2, x="prix_m2", nbins=40,
            color_discrete_sequence=[C["green"]],
            labels={"prix_m2":"Prix au m² (FCFA)"},
        )
        fig_m2.update_traces(marker_line_width=0)
        fig_m2.update_xaxes(tickformat=".2s", title_text="Prix/m² (FCFA)")
        fig_m2.update_yaxes(title_text="Annonces")
    else:
        fig_m2 = empty
    fig_m2.update_layout(**_gl({"l":50,"r":12,"t":12,"b":40}))

    return fig_box, fig_sc, fig_bar, stats_div, fig_src, fig_m2


def register_analytics_dashboard():
    logger.info("AnalyticsDashboard enregistré."); return app
