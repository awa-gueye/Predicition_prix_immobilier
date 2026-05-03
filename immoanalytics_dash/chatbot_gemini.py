"""
ImmoPredict SN — chatbot_gemini.py
Chatbot propulsé par Google Gemini 2.0 Flash.
AUCUNE réponse prédéfinie : tout passe par l'IA.
"""
import re, json, logging, os
import statistics as _st
from collections import defaultdict, Counter
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# CONTEXTE MARCHÉ (injecté dans chaque requête Gemini)
# ══════════════════════════════════════════════════════════════

def _build_context():
    """Résumé du marché immobilier sénégalais pour le prompt."""
    try:
        from properties.models import (
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty,
        )
        data = []
        for M in [CoinAfriqueProperty, ExpatDakarProperty,
                  LogerDakarProperty, DakarVenteProperty]:
            try:
                avail = [f.name for f in M._meta.get_fields()]
                flds = [f for f in ["price","city","property_type"] if f in avail]
                for p in M.objects.filter(price__gte=500000).values(*flds)[:2000]:
                    data.append(p)
            except Exception:
                continue

        if not data:
            return ""

        prices = [float(d["price"]) for d in data if d.get("price")]
        if not prices:
            return ""

        types = Counter(str(d.get("property_type","") or "").strip() for d in data)
        by_city = defaultdict(list)
        for d in data:
            c = str(d.get("city","") or "").strip().title()
            if c and c != "Inconnu":
                by_city[c].append(float(d["price"]))

        top = sorted(
            [(c, _st.median(ps), len(ps))
             for c, ps in by_city.items() if len(ps) >= 5],
            key=lambda x: x[1], reverse=True,
        )[:10]

        def fmt(p):
            if p >= 1e9: return f"{p/1e9:.1f} Mds"
            if p >= 1e6: return f"{p/1e6:.1f}M"
            if p >= 1e3: return f"{p/1e3:.0f}K"
            return str(int(p))

        return (
            f"DONNÉES RÉELLES DU MARCHÉ IMMOBILIER SÉNÉGALAIS :\n"
            f"• {len(data):,} annonces indexées\n"
            f"• Prix médian : {fmt(_st.median(prices))} FCFA\n"
            f"• Fourchette : {fmt(min(prices))} – {fmt(max(prices))} FCFA\n\n"
            f"Types : " + ", ".join(f"{t} ({n})" for t, n in types.most_common(5)) + "\n\n"
            f"Prix médians par quartier :\n"
            + "\n".join(f"• {c}: {fmt(p)} FCFA ({n} ann.)" for c, p, n in top)
            + "\n\nRepères :\n"
            "• Villa Almadies : 150–500M | Loyer 1–5M/mois\n"
            "• Appt Mermoz : 40–120M | Loyer 200–800K/mois\n"
            "• Studio Plateau : 10–35M | Loyer 60–200K/mois\n"
            "• Terrain Pikine : 3–25M FCFA"
        )
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
# PROMPT SYSTÈME
# ══════════════════════════════════════════════════════════════

SYSTEM = """Tu es ImmoAI, l'assistant intelligent de ImmoPredict SN,
la première plateforme IA dédiée au marché immobilier sénégalais.

Tu es un assistant polyvalent comme ChatGPT ou Claude.
Tu réponds à ABSOLUMENT TOUTES les questions : immobilier,
culture générale, mathématiques, histoire, géographie, sciences,
actualités, cuisine, sport, programmation, droit, santé, etc.

RÈGLES :
1. Réponds TOUJOURS en français
2. Ne dis JAMAIS "je ne comprends pas" ou "je ne peux pas"
3. Structure tes réponses clairement avec des paragraphes
4. Utilise du gras **texte** pour les points importants
5. Pour l'immobilier sénégalais, appuie-toi sur les données réelles
6. Formate les prix en FCFA (85M FCFA, 300K FCFA)
7. Si on te demande un calcul, fais-le précisément
8. Sois chaleureux et professionnel
9. Tu peux donner des opinions et recommandations argumentées
10. Adapte la longueur de ta réponse à la question"""


# ══════════════════════════════════════════════════════════════
# APPEL GEMINI
# ══════════════════════════════════════════════════════════════

def _call_gemini(question, history=None):
    """Envoie la question à Gemini et retourne la réponse."""
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY manquante")

    genai.configure(api_key=api_key)

    ctx = _build_context()
    full_prompt = SYSTEM
    if ctx:
        full_prompt += "\n\n" + ctx

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=full_prompt,
    )

    # Historique de conversation
    chat_history = []
    if history:
        for msg in history[-10:]:
            role = "user" if msg.get("role") == "user" else "model"
            content = msg.get("content", "")
            if content:
                chat_history.append({"role": role, "parts": [content]})

    chat = model.start_chat(history=chat_history)
    response = chat.send_message(question)
    return response.text


def _md_to_html(text):
    """Markdown Gemini → HTML."""
    if not text:
        return ""
    t = text
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    t = re.sub(r'^\s*[-•]\s+', '• ', t, flags=re.MULTILINE)
    t = t.replace('\n\n', '<br><br>').replace('\n', '<br>')
    t = re.sub(r'```\w*\n?', '', t)
    return t


# ══════════════════════════════════════════════════════════════
# ENDPOINT
# ══════════════════════════════════════════════════════════════

@login_required(login_url="/immo/login/")
def api_chatbot(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST requis"}, status=405)

    try:
        body = json.loads(request.body)
        question = body.get("message", "").strip()
        history = body.get("history", [])

        if not question:
            return JsonResponse({"error": "Message vide"}, status=400)

        # Tout passe par Gemini — aucune réponse prédéfinie
        try:
            raw = _call_gemini(question, history)
            return JsonResponse({
                "response": _md_to_html(raw),
                "total": 0,
                "properties": [],
            })
        except EnvironmentError:
            # Clé API non configurée
            return JsonResponse({
                "response": (
                    "Le chatbot IA n'est pas encore activé.<br><br>"
                    "L'administrateur doit configurer la variable "
                    "<b>GEMINI_API_KEY</b> dans les paramètres du serveur.<br><br>"
                    "Clé gratuite sur "
                    "<a href='https://aistudio.google.com/apikey' "
                    "target='_blank' style='color:#1A8ED8'>"
                    "aistudio.google.com</a>"
                ),
                "total": 0,
                "properties": [],
            })
        except Exception as e:
            logger.error(f"Gemini: {e}")
            return JsonResponse({
                "response": f"Erreur temporaire du service IA. Réessayez. <br><small style='color:#999'>{str(e)[:80]}</small>",
                "total": 0,
                "properties": [],
            })

    except Exception as e:
        logger.error(f"Chatbot: {e}")
        return JsonResponse({
            "response": "Erreur. Réessayez.",
            "total": 0,
            "properties": [],
        })
