"""
ImmoPredict SN — chatbot_gemini.py
Chatbot ImmoAI propulsé par Google Gemini (gemini-2.0-flash).
Assistant polyvalent : immobilier sénégalais, culture générale, calculs, conseils.
Fallback local intelligent quand l'API n'est pas disponible.
"""
import re, json, logging, os
import statistics as stats
from collections import defaultdict, Counter
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)

PRICE_MIN = 500_000
PRICE_MAX = 5_000_000_000
GEMINI_MODEL = "gemini-2.0-flash"


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(p):
    if not p or float(p) < 100:
        return "—"
    p = float(p)
    if p >= 1e9:
        return f"{p / 1e9:.2f} Mds FCFA"
    if p >= 1e6:
        return f"{p / 1e6:.1f}M FCFA"
    if p >= 1e3:
        return f"{p / 1e3:.0f}K FCFA"
    return f"{p:,.0f} FCFA"


def _md_to_html(text):
    """Convertit le markdown Gemini en HTML simple."""
    if not text:
        return ""
    t = text
    # Bold
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    # Italic
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    # Bullet lists
    t = re.sub(r'^\s*[-•]\s+', '• ', t, flags=re.MULTILINE)
    # Numbered lists
    t = re.sub(r'^\s*(\d+)\.\s+', r'\1. ', t, flags=re.MULTILINE)
    # Line breaks
    t = t.replace('\n\n', '<br><br>')
    t = t.replace('\n', '<br>')
    # Clean up
    t = re.sub(r'```\w*\n?', '', t)
    return t


CITIES_SN = [
    "almadies", "ngor", "ouakam", "mermoz", "pikine", "guédiawaye", "plateau",
    "fann", "yoff", "rufisque", "liberté", "hlm", "sicap", "grand yoff",
    "keur massar", "médina", "thiès", "mbour", "dakar", "parcelles",
    "sacré coeur", "vdn", "saly", "patte d'oie", "diamniadio",
]


# ══════════════════════════════════════════════════════════════════════════════
# ACCÈS AUX DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

def _get_db_data():
    try:
        from properties.models import (
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty,
        )
        results = []
        for model in [CoinAfriqueProperty, ExpatDakarProperty,
                      LogerDakarProperty, DakarVenteProperty]:
            try:
                avail = [f.name for f in model._meta.get_fields()]
                fields = [f for f in ["price", "city", "property_type",
                                      "surface_area", "bedrooms", "title"]
                          if f in avail]
                for p in model.objects.filter(
                    price__gte=PRICE_MIN, price__lte=PRICE_MAX
                ).values(*fields)[:2000]:
                    results.append(p)
            except Exception:
                continue
        return results
    except Exception:
        return []


def _build_market_context():
    """Construit le résumé du marché pour alimenter le prompt Gemini."""
    data = _get_db_data()
    if not data:
        return "Base de données ImmoPredict SN : données en cours de chargement."

    prices = [float(d["price"]) for d in data if d.get("price")]
    if not prices:
        return "Données de prix insuffisantes."

    types = Counter(
        str(d.get("property_type", "") or "").strip() for d in data
    )
    by_city = defaultdict(list)
    for d in data:
        c = str(d.get("city", "") or "").strip().title()
        if c and c != "Inconnu":
            by_city[c].append(float(d["price"]))

    top = sorted(
        [(c, stats.median(ps), len(ps))
         for c, ps in by_city.items() if len(ps) >= 5],
        key=lambda x: x[1], reverse=True,
    )[:10]

    return (
        f"DONNÉES DU MARCHÉ IMMOBILIER SÉNÉGALAIS "
        f"(ImmoPredict SN — données réelles) :\n"
        f"• Total annonces : {len(data):,}\n"
        f"• Prix médian : {_fmt(stats.median(prices))}\n"
        f"• Prix moyen : {_fmt(stats.mean(prices))}\n"
        f"• Fourchette : {_fmt(min(prices))} à {_fmt(max(prices))}\n\n"
        f"Types de biens :\n"
        + "\n".join(f"• {t}: {n} annonces"
                    for t, n in types.most_common(6))
        + "\n\nPrix médians par quartier :\n"
        + "\n".join(f"• {c}: {_fmt(p)} ({n} ann.)"
                    for c, p, n in top)
        + "\n\nRepères Dakar :\n"
        "• Villa Almadies : 150–500M FCFA | Loyer 1–5M/mois\n"
        "• Appartement Mermoz : 40–120M | Loyer 200–800K/mois\n"
        "• Studio Plateau : 10–35M | Loyer 60–200K/mois\n"
        "• Terrain Pikine : 3–25M FCFA\n"
        "• Chambre (loyer) : 30–150K/mois"
    )


# ══════════════════════════════════════════════════════════════════════════════
# APPEL GOOGLE GEMINI
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_INSTRUCTION = """Tu es ImmoAI, l'assistant intelligent de la plateforme ImmoPredict SN,
la première plateforme d'intelligence artificielle dédiée au marché immobilier sénégalais.

TU ES UN ASSISTANT POLYVALENT. Tu réponds à TOUTES les questions sans exception :
immobilier, culture générale, mathématiques, histoire, géographie, sciences,
actualités, cuisine, sport, programmation, droit, fiscalité, etc.

RÈGLES STRICTES :
1. Tu réponds TOUJOURS en français.
2. Tu ne dis JAMAIS « je ne comprends pas » ou « je ne peux pas répondre ».
3. Pour l'immobilier sénégalais, tu t'appuies sur les données réelles fournies.
4. Pour tout autre sujet, tu utilises tes connaissances générales.
5. Tu formates les prix en FCFA (85M FCFA, 300K FCFA).
6. Tu structures tes réponses : titres en gras, listes à puces, chiffres clés.
7. Tu es chaleureux, professionnel et précis.
8. Si on te demande un calcul, tu le fais étape par étape.
9. Si on te demande une comparaison, tu la structures clairement.
10. Tu peux donner des recommandations d'investissement argumentées.

COMPÉTENCES SPÉCIALES IMMOBILIER :
- Estimation de prix par quartier, type et superficie
- Calcul de rentabilité locative (loyer×12 / prix × 100)
- Calcul de mensualités de crédit
- Comparaison de quartiers (prix, ambiance, commodités)
- Conseils d'investissement basés sur les données
- Frais de notaire au Sénégal (6–8 % du prix)
- Démarches administratives d'achat/vente/location"""


def _gemini_response(question, context, history=None):
    """Appelle l'API Google Gemini et renvoie la réponse en texte."""
    try:
        import google.generativeai as genai

        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if not api_key:
            logger.info("GEMINI_API_KEY non configurée — fallback local")
            return None

        genai.configure(api_key=api_key)

        full_instruction = SYSTEM_INSTRUCTION + "\n\n" + context

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=full_instruction,
        )

        # Reconstruire l'historique de conversation
        chat_history = []
        if history:
            for msg in history[-8:]:
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                if content:
                    chat_history.append({
                        "role": role,
                        "parts": [content],
                    })

        chat = model.start_chat(history=chat_history)
        response = chat.send_message(question)
        return response.text

    except ImportError:
        logger.warning(
            "google-generativeai n'est pas installé. "
            "Exécutez : pip install google-generativeai"
        )
        return None
    except Exception as e:
        logger.warning(f"Erreur Gemini : {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FALLBACK LOCAL (sans API)
# ══════════════════════════════════════════════════════════════════════════════

def _local_response(question):
    """Réponse locale quand aucune API n'est disponible."""
    ql = question.lower()

    data = _get_db_data()
    prices = [d["price"] for d in data
              if d.get("price") and d["price"] >= PRICE_MIN]

    if not prices:
        return ("Base de données en cours de chargement. "
                "Réessayez dans quelques instants."), []

    city = next(
        (c.title() for c in CITIES_SN if c in ql),
        None,
    )

    # ── Prix / Estimation ─────────────────────────────────────
    if any(w in ql for w in
           ["prix", "valeur", "coût", "combien", "vaut", "coûte", "estime"]):
        filtered = data
        if city:
            filtered = [d for d in data
                        if city.lower()[:5]
                        in str(d.get("city", "")).lower()]
        fp = [d["price"] for d in filtered if d.get("price")]
        if fp:
            scope = f" à <b>{city}</b>" if city else ""
            return (
                f"<b>Prix{scope}</b> ({len(fp)} annonces) :<br>"
                f"• Médiane : <b>{_fmt(stats.median(fp))}</b><br>"
                f"• Minimum : <b>{_fmt(min(fp))}</b><br>"
                f"• Maximum : <b>{_fmt(max(fp))}</b>"
            ), []

    # ── Comparaison / Quartiers ───────────────────────────────
    if any(w in ql for w in
           ["cher", "abordable", "moins cher", "comparer", "quartier"]):
        by_city = defaultdict(list)
        for d in data:
            c = str(d.get("city", "") or "").strip().title()
            if c and c != "Inconnu" and d.get("price"):
                by_city[c].append(d["price"])
        ranked = sorted(
            [(c, stats.median(ps), len(ps))
             for c, ps in by_city.items() if len(ps) >= 3],
            key=lambda x: x[1],
        )
        if ranked:
            lines = ["<b>Quartiers les plus abordables :</b>"]
            for c, med, n in ranked[:5]:
                lines.append(f"• {c} : <b>{_fmt(med)}</b> ({n} ann.)")
            lines.append("<br><b>Quartiers les plus chers :</b>")
            for c, med, n in ranked[-5:][::-1]:
                lines.append(f"• {c} : <b>{_fmt(med)}</b> ({n} ann.)")
            return "<br>".join(lines), []

    # ── Biens récents ─────────────────────────────────────────
    if any(w in ql for w in ["récent", "nouveau", "dernier"]):
        lines = ["<b>Biens récents :</b>"]
        for d in data[:8]:
            lines.append(
                f"• <b>{_fmt(d.get('price', 0))}</b> — "
                f"{d.get('property_type', '')} à "
                f"{str(d.get('city', '')).strip().title()}"
            )
        return "<br>".join(lines), []

    # ── Statistiques / Résumé ─────────────────────────────────
    if any(w in ql for w in
           ["statistique", "marché", "résumé", "aperçu", "tendance"]):
        types = Counter(
            str(d.get("property_type", "") or "").strip()
            for d in data if d.get("price")
        )
        lines = [
            f"<b>Marché ImmoPredict SN</b> ({len(data):,} annonces) :",
            f"• Prix médian : <b>{_fmt(stats.median(prices))}</b>",
            f"• Prix moyen : <b>{_fmt(stats.mean(prices))}</b>",
            f"• De {_fmt(min(prices))} à {_fmt(max(prices))}",
            "", "<b>Types :</b>",
        ]
        for t, n in types.most_common(5):
            lines.append(f"• {t or 'Autre'} : {n:,}")
        return "<br>".join(lines), []

    # ── Rentabilité ───────────────────────────────────────────
    if any(w in ql for w in ["rentabilité", "rendement", "roi"]):
        nums = [float(n.replace(",", "."))
                for n in re.findall(r"[\d]+(?:[.,]\d+)?",
                                    ql.replace(" ", ""))]
        if len(nums) >= 2:
            prix = nums[0] * 1e6 if nums[0] < 100_000 else nums[0]
            loyer = nums[1] * 1_000 if nums[1] < 100_000 else nums[1]
            renta = (loyer * 12 / prix) * 100
            return (
                f"<b>Calcul de rentabilité</b><br>"
                f"• Prix : <b>{_fmt(prix)}</b><br>"
                f"• Loyer : <b>{_fmt(loyer)}/mois</b><br>"
                f"• Rentabilité brute : <b>{renta:.1f} %</b><br>"
                f"• Retour sur investissement : "
                f"<b>{prix / (loyer * 12):.1f} ans</b>"
            ), []

    # ── Réponse par défaut : résumé du marché ─────────────────
    return (
        f"<b>ImmoPredict SN</b> — {len(data):,} annonces<br>"
        f"Prix médian : <b>{_fmt(stats.median(prices))}</b><br><br>"
        f"Posez-moi une question précise :<br>"
        f"• <em>Que vaut un appartement à Mermoz ?</em><br>"
        f"• <em>Quel quartier est le moins cher ?</em><br>"
        f"• <em>Calcule la rentabilité d'un bien "
        f"à 80M loué 500K/mois</em><br><br>"
        f"<em>Pour des réponses illimitées, demandez à l'administrateur "
        f"de configurer GEMINI_API_KEY.</em>"
    ), []


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url="/immo/login/")
def api_chatbot(request):
    """Point d'entrée du chatbot ImmoAI."""
    if request.method != "POST":
        return JsonResponse({"error": "POST requis"}, status=405)

    try:
        body = json.loads(request.body)
        q = body.get("message", "").strip()
        hist = body.get("history", [])

        if not q:
            return JsonResponse({"error": "Message vide"}, status=400)

        # ── Salutation ────────────────────────────────────────
        greetings = {
            "bonjour", "bonsoir", "salut", "hello", "hi", "coucou",
            "merci", "ok", "cc", "hey", "yo", "wesh", "slt",
        }
        if q.lower().strip().rstrip("!?.,;:") in greetings or len(q) < 4:
            return JsonResponse({
                "response": (
                    "Bonjour ! Je suis <b>ImmoAI</b>, "
                    "votre assistant intelligent.<br><br>"
                    "Je réponds à <b>toutes vos questions</b> :<br>"
                    "• Immobilier : prix, quartiers, estimations<br>"
                    "• Calculs : rentabilité, mensualités, frais<br>"
                    "• Conseils : où investir, démarches<br>"
                    "• Culture générale, et bien plus !<br><br>"
                    "<em>Essayez : Que vaut une villa aux Almadies ?</em>"
                ),
                "total": 0,
                "properties": [],
            })

        # ── Essayer Gemini ────────────────────────────────────
        context = _build_market_context()
        gemini_resp = _gemini_response(q, context, hist)

        if gemini_resp:
            return JsonResponse({
                "response": _md_to_html(gemini_resp),
                "total": 0,
                "properties": [],
                "source": "gemini",
            })

        # ── Fallback local ────────────────────────────────────
        resp, props = _local_response(q)
        return JsonResponse({
            "response": resp,
            "total": len(props),
            "properties": props,
            "source": "local",
        })

    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        return JsonResponse({
            "response": "Une erreur s'est produite. Réessayez.",
            "total": 0,
            "properties": [],
        })
