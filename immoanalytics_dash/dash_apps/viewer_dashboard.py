"""
Dashboard Recherche IA — DjangoDash("ViewerDashboard")
Chatbot NLP + filtres avancés + grille de résultats.
Accessible à tous les rôles.
"""
import re, logging
import pandas as pd
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)

# Réutilise _load_data et _demo_data du main_dashboard
def _load():
    try:
        from .main_dashboard import _load_data
        return _load_data()
    except Exception:
        from .main_dashboard import _demo_data
        return _demo_data()


# ── NLP ───────────────────────────────────────────────────────────────────────

CITIES_SN = [
    "almadies","ngor","ouakam","mermoz","pikine","guediawaye","plateau","fann",
    "yoff","rufisque","liberte","hlm","sicap","grand yoff","keur massar",
    "medina","thies","mbour","saint-louis","parcelles","sacre coeur","point e",
    "vdn","hann","yeumbeul","malika","saly","dakar",
]

TYPE_MAP = {
    "villa":      ["villa"],
    "appartement":["appart","f2","f3","f4","f5"],
    "terrain":    ["terrain","parcelle"],
    "duplex":     ["duplex"],
    "studio":     ["studio"],
    "maison":     ["maison"],
}

KW_LOC = ["louer","location","locat","bail","mensuel","mois","loue","loyer"]
KW_VTE = ["vendre","acheter","achat","vente","acquérir","acquisition"]


def _amt(t):
    try:
        v = float(str(t).replace(" ","").replace(",","."))
        return v * 1_000_000 if v < 10_000 else v
    except Exception:
        return None


def _parse(text: str) -> dict:
    tl = text.lower().replace("é","e").replace("è","e").replace("à","a")

    # Budget
    mn = mx = None
    m = re.search(r"entre\s+([\d\s,.]+)\s*(?:et|-)\s*([\d\s,.]+)\s*(?:m|milli|fcfa)?", tl)
    if m:
        mn, mx = _amt(m.group(1)), _amt(m.group(2))
    else:
        m2 = re.search(r"(?:moins de|max)\s+([\d\s,.]+)\s*(?:m|milli)?", tl)
        if m2: mx = _amt(m2.group(1))
        m3 = re.search(r"(?:a partir de|plus de|min)\s+([\d\s,.]+)\s*(?:m|milli)?", tl)
        if m3: mn = _amt(m3.group(1))
        if not m2 and not m3:
            m4 = re.search(r"([\d]+)\s*(?:m\b|millions?)", tl)
            if m4:
                v = _amt(m4.group(1)); mn = v*.7; mx = v*1.3

    city  = next((c.title() for c in sorted(CITIES_SN,key=len,reverse=True) if c in tl), None)
    ptype = next((k.capitalize() for k,kws in TYPE_MAP.items()
                  if any(kw in tl for kw in [k]+kws)), None)
    txn   = ("location" if any(k in tl for k in KW_LOC) else
             "vente"    if any(k in tl for k in KW_VTE) else None)

    beds = None
    mb = re.search(r"(\d+)\s*chambre", tl)
    if mb: beds = int(mb.group(1))
    mb2 = re.search(r"[ft](\d)", tl)
    if mb2: beds = max(1, int(mb2.group(1))-1)

    return {"city":city,"type":ptype,"transaction":txn,
            "min_price":mn,"max_price":mx,"bedrooms":beds}


def _fmt(p) -> str:
    if p is None or (isinstance(p, float) and pd.isna(p)): return "—"
    return f"{float(p)/1e6:.1f}M FCFA" if float(p) >= 1_000_000 else f"{float(p):,.0f} FCFA"


def _prop_card(row: dict) -> dbc.Card:
    txn_c = "#27AE60" if row.get("transaction")=="vente" else "#3498DB"
    txn_l = "🛒 Vente" if row.get("transaction")=="vente" else "🔑 Location"
    feats = []
    if pd.notna(row.get("bedrooms"))    and row["bedrooms"]    > 0:
        feats.append(html.Span(f"🛏 {int(row['bedrooms'])} ch.",
                               style={"background":"rgba(27,58,45,.06)","padding":".18rem .45rem","fontSize":".73rem","borderRadius":"2px"}))
    if pd.notna(row.get("surface_area")) and row["surface_area"] > 0:
        feats.append(html.Span(f"📐 {row['surface_area']:.0f} m²",
                               style={"background":"rgba(27,58,45,.06)","padding":".18rem .45rem","fontSize":".73rem","borderRadius":"2px"}))
    return dbc.Card(dbc.CardBody([
        html.Div([
            html.Span(txn_l, style={"background":txn_c,"color":"white","padding":".18rem .5rem","fontSize":".68rem","borderRadius":"2px"}),
            html.Span(str(row.get("source","")).replace("_"," ").title(),
                      style={"background":"rgba(27,58,45,.06)","color":"#8A8070","padding":".18rem .4rem","fontSize":".65rem","borderRadius":"2px","marginLeft":".4rem","fontFamily":"Space Mono,monospace"}),
        ], style={"marginBottom":".6rem"}),
        html.H6(str(row.get("title","Annonce immobilière"))[:55],
                style={"fontSize":".88rem","fontWeight":"500","color":"#2C3E50","marginBottom":".25rem"}),
        html.P(f"📍 {row.get('city','—')} · {row.get('property_type','—')}",
               style={"fontSize":".77rem","color":"#8A8070","marginBottom":".5rem"}),
        html.Div(feats, style={"display":"flex","gap":".3rem","flexWrap":"wrap","marginBottom":".55rem"}),
        html.H5(_fmt(row.get("price")),
                style={"fontFamily":"Cormorant Garamond,serif","fontSize":"1.3rem",
                       "fontWeight":"600","color":"#C9A84C","margin":"0"}),
    ]), style={"border":"1px solid rgba(27,58,45,.1)","borderRadius":"4px",
               "marginBottom":".8rem","cursor":"pointer",
               "transition":"box-shadow .2s",
               "boxShadow":"0 2px 6px rgba(27,58,45,.06)"})


def register_viewer_dashboard():
    app = DjangoDash(
        name="ViewerDashboard",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        add_bootstrap_links=True,
    )

    SUGGESTIONS = [
        "Appartement Dakar 50-100M",
        "Villa Almadies avec piscine",
        "Terrain moins de 30M",
        "Location Ouakam 4 chambres",
    ]

    app.layout = html.Div([
        dcc.Store(id="vd-crit", data={}),
        dbc.Row([
            # ── Colonne gauche : chat + filtres ───────────────────────────────
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-robot me-2", style={"color":"#C9A84C"}),
                        "Assistant IA Immobilier",
                    ], style={"background":"#1B3A2D","color":"#C9A84C","fontWeight":"500"}),
                    dbc.CardBody([
                        # Historique chat
                        html.Div([
                            html.Div([
                                html.Div("🤖", style={"width":"30px","height":"30px","borderRadius":"50%","background":"#1B3A2D","display":"flex","alignItems":"center","justifyContent":"center","fontSize":".8rem","flexShrink":"0"}),
                                html.Div(
                                    "Bonjour ! Décrivez le bien recherché. "
                                    "Ex : « appartement Dakar 50-100M » ou « villa Almadies avec piscine ».",
                                    style={"background":"rgba(27,58,45,.06)","padding":".6rem .9rem","borderRadius":"4px","fontSize":".84rem","color":"#2C3E50","flex":"1"}
                                ),
                            ], style={"display":"flex","gap":".6rem"}),
                        ], id="vd-chat", style={"height":"230px","overflowY":"auto","padding":".5rem",
                                                "display":"flex","flexDirection":"column","gap":".5rem"}),

                        # Saisie
                        html.Div([
                            dcc.Input(id="vd-input", type="text", debounce=False, n_submit=0,
                                      placeholder="Décrivez votre recherche...",
                                      style={"flex":"1","border":"1.5px solid rgba(27,58,45,.15)",
                                             "padding":".6rem .9rem","fontFamily":"DM Sans,sans-serif",
                                             "fontSize":".87rem","borderRadius":"4px","outline":"none"}),
                            html.Button("➤", id="vd-send", n_clicks=0,
                                        style={"background":"#1B3A2D","color":"#C9A84C","border":"none",
                                               "width":"38px","height":"38px","borderRadius":"50%",
                                               "cursor":"pointer","fontSize":"1rem","flexShrink":"0"}),
                        ], style={"display":"flex","gap":".4rem","padding":".6rem 0 .4rem"}),

                        # Suggestions rapides
                        html.Div([
                            html.Small("Suggestions :", style={"color":"#8A8070","marginRight":".4rem"}),
                            *[html.Button(s, id=f"vd-sug-{i}", n_clicks=0,
                                          style={"background":"rgba(201,168,76,.1)","border":"1px solid rgba(201,168,76,.3)",
                                                 "color":"#2C3E50","padding":".2rem .6rem","fontSize":".72rem",
                                                 "borderRadius":"20px","cursor":"pointer","marginRight":".3rem","marginBottom":".3rem"})
                              for i, s in enumerate(SUGGESTIONS)]
                        ], style={"display":"flex","flexWrap":"wrap","alignItems":"center"}),
                    ]),
                ], className="mb-3"),

                # Filtres manuels
                dbc.Card([
                    dbc.CardHeader([
                        html.I(className="fas fa-sliders-h me-2"),
                        "Filtres avancés",
                        html.Button(
                            [html.I(className="fas fa-redo me-1"), "Réinit."],
                            id="vd-reset", n_clicks=0,
                            style={"background":"transparent","border":"1px solid rgba(231,76,60,.3)",
                                   "color":"#e74c3c","padding":".2rem .6rem","fontSize":".73rem",
                                   "borderRadius":"2px","cursor":"pointer","float":"right"},
                        ),
                    ]),
                    dbc.CardBody([
                        html.Label("Ville / Quartier", style={"fontSize":".72rem","textTransform":"uppercase","letterSpacing":".1em","color":"#8A8070","fontFamily":"Space Mono,monospace"}),
                        dcc.Dropdown(id="vd-city",  placeholder="Toutes", multi=True, className="mb-3"),
                        html.Label("Type de bien", style={"fontSize":".72rem","textTransform":"uppercase","letterSpacing":".1em","color":"#8A8070","fontFamily":"Space Mono,monospace"}),
                        dcc.Dropdown(id="vd-type",
                                     options=[{"label":t,"value":t} for t in
                                              ["Villa","Appartement","Terrain","Duplex","Studio","Maison"]],
                                     placeholder="Tous les types", multi=True, className="mb-3"),
                        html.Label("Transaction", style={"fontSize":".72rem","textTransform":"uppercase","letterSpacing":".1em","color":"#8A8070","fontFamily":"Space Mono,monospace"}),
                        dcc.RadioItems(id="vd-txn",
                                       options=[{"label":" Tout","value":"all"},
                                                {"label":" Vente","value":"vente"},
                                                {"label":" Location","value":"location"}],
                                       value="all", inline=True, className="mb-3"),
                        html.Label("Budget (M FCFA)", style={"fontSize":".72rem","textTransform":"uppercase","letterSpacing":".1em","color":"#8A8070","fontFamily":"Space Mono,monospace"}),
                        dcc.RangeSlider(id="vd-price", min=0, max=500, step=5, value=[0,500],
                                        marks={0:"0",100:"100M",200:"200M",300:"300M",500:"500M+"}, className="mb-3"),
                        html.Label("Chambres min.", style={"fontSize":".72rem","textTransform":"uppercase","letterSpacing":".1em","color":"#8A8070","fontFamily":"Space Mono,monospace"}),
                        dcc.Slider(id="vd-beds", min=0, max=8, step=1, value=0,
                                   marks={i:str(i) for i in range(9)}, className="mb-1"),
                    ]),
                ]),
            ], md=4),

            # ── Colonne droite : résultats ─────────────────────────────────────
            dbc.Col([
                html.Div(id="vd-header", className="mb-3"),
                html.Div(id="vd-results"),
            ], md=8),
        ], style={"padding":"1.5rem","background":"#F0F4F0","minHeight":"100vh","margin":"0"}),
    ])

    # ── Callbacks ─────────────────────────────────────────────────────────────

    @app.callback(Output("vd-city","options"), Input("vd-price","value"))
    def load_cities(_):
        df = _load()
        return [{"label":c,"value":c} for c in sorted(df["city"].dropna().unique())]

    @app.callback(
        [Output("vd-chat","children"), Output("vd-crit","data"),
         Output("vd-input","value"),
         Output("vd-city","value"),   Output("vd-type","value"),
         Output("vd-txn","value"),    Output("vd-price","value"),
         Output("vd-beds","value")],
        [Input("vd-send","n_clicks"), Input("vd-input","n_submit"),
         Input("vd-sug-0","n_clicks"), Input("vd-sug-1","n_clicks"),
         Input("vd-sug-2","n_clicks"), Input("vd-sug-3","n_clicks")],
        [State("vd-input","value"), State("vd-chat","children")],
        prevent_initial_call=True,
    )
    def on_chat(ns, nss, s0, s1, s2, s3, text, history):
        from dash import ctx
        tid = ctx.triggered_id
        # Suggestion rapide
        for i, sug in enumerate(SUGGESTIONS):
            if tid == f"vd-sug-{i}":
                text = sug
                break
        if not text or not text.strip():
            from dash.exceptions import PreventUpdate
            raise PreventUpdate

        crit = _parse(text)
        df   = _load()
        dff  = df.copy()
        if crit.get("city"):        dff = dff[dff["city"].str.lower() == crit["city"].lower()]
        if crit.get("type"):        dff = dff[dff["property_type"].str.lower() == crit["type"].lower()]
        if crit.get("transaction"): dff = dff[dff["transaction"] == crit["transaction"]]
        if crit.get("min_price"):   dff = dff[dff["price"] >= crit["min_price"]]
        if crit.get("max_price"):   dff = dff[dff["price"] <= crit["max_price"]]
        if crit.get("bedrooms"):    dff = dff[dff["bedrooms"] >= crit["bedrooms"]]
        n = len(dff)

        parts = ["Critères :"]
        if crit.get("city"):        parts.append(f"📍{crit['city']}")
        if crit.get("type"):        parts.append(f"🏠{crit['type']}")
        if crit.get("transaction"): parts.append(f"📋{crit['transaction']}")
        mn, mx = crit.get("min_price"), crit.get("max_price")
        if mn and mx: parts.append(f"💰{mn/1e6:.0f}M–{mx/1e6:.0f}M FCFA")
        elif mx:      parts.append(f"💰Max {mx/1e6:.0f}M FCFA")
        response = " · ".join(parts) + f"\n✅ {n:,} résultat{'s' if n>1 else ''}."

        hist = list(history or [])
        hist.append(html.Div([
            html.Div("👤",style={"width":"28px","height":"28px","borderRadius":"50%","background":"#C9A84C","display":"flex","alignItems":"center","justifyContent":"center","fontSize":".75rem","flexShrink":"0"}),
            html.Div(text,style={"background":"#1B3A2D","color":"#E8D5A3","padding":".5rem .8rem","borderRadius":"4px","fontSize":".83rem","flex":"1"}),
        ], style={"display":"flex","gap":".5rem","justifyContent":"flex-end"}))
        hist.append(html.Div([
            html.Div("🤖",style={"width":"28px","height":"28px","borderRadius":"50%","background":"#1B3A2D","display":"flex","alignItems":"center","justifyContent":"center","fontSize":".75rem","flexShrink":"0"}),
            html.Div(response,style={"background":"rgba(27,58,45,.06)","padding":".5rem .8rem","borderRadius":"4px","fontSize":".83rem","color":"#2C3E50","flex":"1","whiteSpace":"pre-line"}),
        ], style={"display":"flex","gap":".5rem"}))

        city_v  = [crit["city"]]          if crit.get("city")        else None
        type_v  = [crit["type"]]          if crit.get("type")        else None
        txn_v   = crit.get("transaction") or "all"
        beds_v  = crit.get("bedrooms")    or 0
        mn_m    = int((crit.get("min_price") or 0)    / 1e6)
        mx_m    = int((crit.get("max_price") or 500e6)/ 1e6)
        price_v = [min(mn_m,500), min(mx_m,500)]

        return hist, crit, "", city_v, type_v, txn_v, price_v, beds_v

    @app.callback(
        [Output("vd-header","children"), Output("vd-results","children")],
        [Input("vd-city","value"), Input("vd-type","value"), Input("vd-txn","value"),
         Input("vd-price","value"), Input("vd-beds","value"), Input("vd-reset","n_clicks")],
    )
    def update_results(cities, types, txn, price, beds, _reset):
        df = _load()
        if cities: df = df[df["city"].isin(cities)]
        if types:  df = df[df["property_type"].isin(types)]
        if txn and txn != "all": df = df[df["transaction"] == txn]
        if price: df = df[df["price"].between(price[0]*1e6, price[1]*1e6)]
        if beds and beds > 0: df = df[df["bedrooms"] >= beds]

        n = len(df)
        header = html.H5(
            f"{n:,} propriété{'s' if n>1 else ''} trouvée{'s' if n>1 else ''}",
            style={"fontWeight":"500","color":"#2C3E50","marginBottom":"1rem"},
        )
        if n == 0:
            grid = html.Div([
                html.Div("🔍", style={"fontSize":"2.5rem","textAlign":"center","marginBottom":".5rem"}),
                html.P("Aucun résultat. Essayez d'élargir vos critères.",
                       style={"textAlign":"center","color":"#8A8070"}),
            ], style={"background":"white","padding":"2rem","borderRadius":"4px",
                      "border":"1px solid rgba(27,58,45,.1)"})
            return header, grid

        cards = [_prop_card(r.to_dict()) for _,r in df.sort_values("price").head(24).iterrows()]
        grid  = html.Div(cards, style={
            "display":"grid","gridTemplateColumns":"repeat(auto-fill,minmax(280px,1fr))","gap":".8rem"})
        return header, grid

    logger.info("ViewerDashboard enregistré.")
    return app
