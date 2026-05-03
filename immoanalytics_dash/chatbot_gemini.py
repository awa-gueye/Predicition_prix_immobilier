"""
ImmoPredict SN — Chatbot Hugging Face
Utilise huggingface_hub (plus fiable que urllib direct).
Modèles non-gated uniquement (pas besoin d'accepter des conditions).
"""
import json, logging, os, re
import statistics as _st
from collections import defaultdict, Counter
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# ── Modèles NON-GATED (aucune acceptation de conditions requise) ──
# Testés et fonctionnels sur le free tier HF
MODELS = [
    "HuggingFaceH4/zephyr-7b-beta",
    "microsoft/Phi-3-mini-4k-instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "tiiuae/falcon-7b-instruct",
]


# ── Contexte marché ───────────────────────────────────────────
def _market_context():
    try:
        from properties.models import (
            CoinAfriqueProperty, ExpatDakarProperty,
            LogerDakarProperty, DakarVenteProperty,
        )
        prices, by_city = [], defaultdict(list)
        for M in [CoinAfriqueProperty, ExpatDakarProperty,
                  LogerDakarProperty, DakarVenteProperty]:
            try:
                avail = [f.name for f in M._meta.get_fields()]
                flds  = [f for f in ["price","city"] if f in avail]
                for p in M.objects.filter(price__gte=500000).values(*flds)[:1000]:
                    if p.get("price"):
                        prices.append(float(p["price"]))
                        c = str(p.get("city","") or "").strip().title()
                        if c and c != "Inconnu":
                            by_city[c].append(float(p["price"]))
            except Exception:
                continue
        if not prices:
            return ""
        def fmt(p):
            if p>=1e9: return f"{p/1e9:.1f}Mds"
            if p>=1e6: return f"{p/1e6:.1f}M"
            if p>=1e3: return f"{p/1e3:.0f}K"
            return str(int(p))
        top = sorted(
            [(c, _st.median(ps)) for c,ps in by_city.items() if len(ps)>=5],
            key=lambda x: x[1], reverse=True)[:6]
        return (
            f"Marché immobilier sénégalais : {len(prices):,} annonces, "
            f"prix médian {fmt(_st.median(prices))} FCFA. "
            "Quartiers : " + ", ".join(f"{c} {fmt(p)} FCFA" for c,p in top)
        )
    except Exception:
        return ""


SYSTEM = (
    "Tu es ImmoAI, assistant intelligent de ImmoPredict SN. "
    "Tu réponds à TOUTES les questions en français (immobilier, culture générale, "
    "calculs, histoire, cuisine, sport, code, etc.). Ne refuse jamais de répondre. "
    "Pour l'immobilier sénégalais, utilise les données du marché fournies."
)


# ── Appel HF avec huggingface_hub ─────────────────────────────
def _call_hf(question, history=None):
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise RuntimeError(
            "Package manquant. Ajoutez 'huggingface-hub' dans requirements.txt "
            "et redéployez."
        )

    api_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
    if not api_key:
        raise EnvironmentError("HUGGINGFACE_API_KEY non configurée")

    ctx     = _market_context()
    sys_msg = SYSTEM + (f" {ctx}" if ctx else "")

    messages = [{"role": "system", "content": sys_msg}]
    if history:
        for m in history[-8:]:
            r = m.get("role","")
            c = m.get("content","").strip()
            if r in ("user","assistant") and c:
                messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": question})

    errors = []
    client = InferenceClient(token=api_key)

    for model in MODELS:
        try:
            resp = client.chat_completion(
                model=model,
                messages=messages,
                max_tokens=800,
                temperature=0.7,
            )
            text = resp.choices[0].message.content.strip()
            if text:
                logger.info(f"ImmoAI: réponse via {model}")
                return text
        except Exception as e:
            err = f"{model}: {e}"
            errors.append(err)
            logger.warning(f"HF échec — {err}")
            continue

    # Tous les modèles ont échoué — remonter les vraies erreurs
    raise RuntimeError("\n".join(errors))


def _to_html(text):
    if not text: return ""
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>', text)
    text = re.sub(r'^#{1,3}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-•]\s+', '• ', text, flags=re.MULTILINE)
    text = text.replace('\n\n','<br><br>').replace('\n','<br>')
    return re.sub(r'```\w*','', text).strip()


# ── Endpoint Django ───────────────────────────────────────────
@login_required(login_url="/immo/login/")
def api_chatbot(request):
    if request.method != "POST":
        return JsonResponse({"error":"POST requis"}, status=405)

    try:
        body     = json.loads(request.body)
        question = body.get("message","").strip()
        history  = body.get("history",[])
        if not question:
            return JsonResponse({"error":"Message vide"}, status=400)

        try:
            raw = _call_hf(question, history)
            return JsonResponse({"response": _to_html(raw),
                                 "total":0, "properties":[]})

        except EnvironmentError as e:
            return JsonResponse({"response":(
                f"<b>Chatbot non configuré</b><br>{e}<br><br>"
                "Ajoutez <b>HUGGINGFACE_API_KEY</b> dans Render → Environment.<br>"
                "Clé gratuite : <a href='https://huggingface.co/settings/tokens' "
                "target='_blank' style='color:#1A8ED8'>huggingface.co/settings/tokens</a>"
            ), "total":0, "properties":[]})

        except RuntimeError as e:
            # Afficher l'erreur réelle pour diagnostic
            detail = str(e)[:400]
            logger.error(f"Tous modèles HF échoués:\n{detail}")
            return JsonResponse({"response":(
                "<b>Erreur IA — Détail :</b><br>"
                f"<code style='font-size:.75rem;color:#C0392B'>{detail}</code><br><br>"
                "Solutions possibles :<br>"
                "• Vérifiez que votre token HF a le droit <b>Read</b><br>"
                "• Acceptez les conditions des modèles sur <a href='https://huggingface.co/HuggingFaceH4/zephyr-7b-beta' target='_blank' style='color:#1A8ED8'>HuggingFaceH4/zephyr-7b-beta</a><br>"
                "• Vérifiez que <b>huggingface-hub</b> est dans requirements.txt"
            ), "total":0, "properties":[]})

    except Exception as e:
        logger.error(f"Chatbot: {e}")
        return JsonResponse({"response":"Erreur. Réessayez.",
                             "total":0, "properties":[]})
