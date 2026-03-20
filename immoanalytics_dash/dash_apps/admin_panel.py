"""
Admin Panel — DjangoDash("AdminPanel")
Gestion des utilisateurs Django, stats données immobilières.
Réservé aux superusers.
"""
import logging
import plotly.express as px
from django_plotly_dash import DjangoDash
from dash import html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc

logger = logging.getLogger(__name__)


def _load():
    try:
        from .main_dashboard import _load_data
        return _load_data()
    except Exception:
        from .main_dashboard import _demo_data
        return _demo_data()


def _base():
    return {
        "paper_bgcolor":"rgba(0,0,0,0)","plot_bgcolor":"rgba(0,0,0,0)",
        "font":{"family":"DM Sans,sans-serif","color":"#2C3E50"},
        "margin":{"l":20,"r":20,"t":30,"b":20},
    }


def register_admin_panel():
    app = DjangoDash(
        name="AdminPanel",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        add_bootstrap_links=True,
    )

    app.layout = html.Div([
        dcc.Interval(id="ap-iv", interval=30_000, n_intervals=0),

        # KPIs système
        html.Div(id="ap-kpis", style={
            "display":"grid","gridTemplateColumns":"repeat(auto-fill,minmax(160px,1fr))",
            "gap":"1rem","marginBottom":"1.5rem",
        }),

        html.Div(id="ap-alert"),

        dbc.Tabs([
            # ── Onglet Utilisateurs ─────────────────────────────────────────
            dbc.Tab(label="👥 Utilisateurs Django", tab_id="tab-users", children=[
                dbc.Card([
                    dbc.CardHeader("➕ Créer un utilisateur"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(dcc.Input(id="ap-uname", placeholder="Username",
                                              className="form-control"), md=3),
                            dbc.Col(dcc.Input(id="ap-email", type="email",
                                              placeholder="Email", className="form-control"), md=3),
                            dbc.Col(dcc.Input(id="ap-pwd",   type="password",
                                              placeholder="Mot de passe", className="form-control"), md=2),
                            dbc.Col(dcc.Dropdown(
                                id="ap-role",
                                options=[{"label":"👑 Admin (superuser)","value":"admin"},
                                         {"label":"📊 Staff (analyst)","value":"staff"},
                                         {"label":"👁️ User (viewer)","value":"user"}],
                                value="user", clearable=False,
                            ), md=2),
                            dbc.Col(dbc.Button("Créer", id="ap-create", color="primary",
                                               n_clicks=0), md=2),
                        ]),
                    ]),
                ], className="mt-3 mb-3"),
                html.Div(id="ap-users-table"),
            ]),

            # ── Onglet Données ──────────────────────────────────────────────
            dbc.Tab(label="📊 Données immobilières", tab_id="tab-data", children=[
                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardHeader("Annonces par source"),
                        dbc.CardBody(dcc.Graph(id="ap-src-chart", config={"displayModeBar":False})),
                    ]), md=6),
                    dbc.Col(dbc.Card([
                        dbc.CardHeader("Répartition vente / location"),
                        dbc.CardBody(dcc.Graph(id="ap-txn-chart", config={"displayModeBar":False})),
                    ]), md=6),
                ], className="mt-3"),
            ]),
        ], id="ap-tabs", active_tab="tab-users"),

    ], style={"padding":"1.5rem","background":"#F0F4F0"})

    # ── Callbacks ─────────────────────────────────────────────────────────────

    @app.callback(
        [Output("ap-kpis","children"),
         Output("ap-users-table","children"),
         Output("ap-alert","children")],
        [Input("ap-iv","n_intervals"), Input("ap-create","n_clicks")],
        [State("ap-uname","value"), State("ap-email","value"),
         State("ap-pwd","value"),   State("ap-role","value")],
    )
    def manage_users(_, n_create, uname, email, pwd, role):
        alert = None

        # Créer un utilisateur Django
        if ctx.triggered_id == "ap-create" and n_create and uname and email and pwd:
            try:
                from django.contrib.auth.models import User as DUser
                if DUser.objects.filter(username=uname).exists():
                    alert = dbc.Alert("Nom d'utilisateur déjà pris.", color="danger", dismissable=True)
                else:
                    u = DUser.objects.create_user(username=uname, email=email, password=pwd)
                    if role == "admin": u.is_superuser = True; u.is_staff = True
                    elif role == "staff": u.is_staff = True
                    u.save()
                    alert = dbc.Alert(f"✅ Utilisateur '{uname}' créé ({role}).",
                                      color="success", dismissable=True)
            except Exception as e:
                alert = dbc.Alert(f"Erreur : {e}", color="danger", dismissable=True)

        # Charger les utilisateurs
        try:
            from django.contrib.auth.models import User as DUser
            users = list(DUser.objects.all().order_by("-date_joined"))
        except Exception:
            users = []

        n_total  = len(users)
        n_active = sum(1 for u in users if u.is_active)
        n_super  = sum(1 for u in users if u.is_superuser)
        n_staff  = sum(1 for u in users if u.is_staff and not u.is_superuser)

        def kpi(val, title, color):
            return html.Div([
                html.H2(str(val), style={"fontFamily":"Cormorant Garamond,serif","fontSize":"2rem","fontWeight":"600","color":"#2C3E50","margin":"0","textAlign":"center"}),
                html.P(title, style={"fontSize":".73rem","color":"#8A8070","textAlign":"center","margin":"0"}),
            ], style={"background":"white","padding":"1.1rem","borderLeft":f"4px solid {color}","boxShadow":"0 2px 8px rgba(27,58,45,.08)","borderRadius":"2px"})

        df   = _load()
        kpis = [
            kpi(n_total,  "Utilisateurs",   "#3498DB"),
            kpi(n_active, "Actifs",          "#27AE60"),
            kpi(n_super,  "Admins",          "#E74C3C"),
            kpi(n_staff,  "Staff",           "#9B59B6"),
            kpi(f"{len(df):,}", "Annonces",  "#C9A84C"),
        ]

        # Table utilisateurs
        rows = []
        for u in users:
            if u.is_superuser:    rl, rc = "👑 Admin",   "#E74C3C"
            elif u.is_staff:      rl, rc = "📊 Staff",   "#3498DB"
            else:                 rl, rc = "👁️ User",   "#27AE60"
            rows.append(html.Tr([
                html.Td(u.id,  style={"fontSize":".8rem"}),
                html.Td(u.username, style={"fontWeight":"500"}),
                html.Td(u.email or "—", style={"fontSize":".8rem"}),
                html.Td(u.get_full_name() or "—", style={"fontSize":".8rem"}),
                html.Td(html.Span(rl, style={"color":rc,"fontWeight":"600","fontSize":".82rem"})),
                html.Td(html.Span("✅ Actif" if u.is_active else "❌ Inactif",
                                  style={"fontSize":".78rem","color":"#27ae60" if u.is_active else "#e74c3c"})),
                html.Td(u.date_joined.strftime("%d/%m/%Y") if u.date_joined else "—",
                        style={"fontSize":".78rem"}),
                html.Td(u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "Jamais",
                        style={"fontSize":".78rem"}),
            ]))

        table = dbc.Table(
            [html.Thead(html.Tr([html.Th(h) for h in
                                 ["ID","Username","Email","Nom","Rôle","Statut","Inscrit","Dernière cnx"]])),
             html.Tbody(rows if rows else [html.Tr([html.Td("Aucun utilisateur", colSpan=8)])])],
            striped=True, hover=True, responsive=True, size="sm",
        )
        return kpis, table, alert

    @app.callback(
        [Output("ap-src-chart","figure"), Output("ap-txn-chart","figure")],
        Input("ap-iv","n_intervals"),
    )
    def data_charts(_):
        df   = _load()
        sc   = df["source"].value_counts().reset_index(); sc.columns = ["s","c"]
        fig_s = px.bar(sc, x="s", y="c", color_discrete_sequence=["#C9A84C"],
                       labels={"s":"Source","c":"Annonces"})
        fig_s.update_layout(**_base())

        tc    = df["transaction"].value_counts().reset_index(); tc.columns = ["t","c"]
        fig_t = px.pie(tc, values="c", names="t", hole=.4,
                       color_discrete_sequence=["#27AE60","#3498DB","#BDC3C7"])
        fig_t.update_layout(**_base())
        return fig_s, fig_t

    logger.info("AdminPanel enregistré.")
    return app
