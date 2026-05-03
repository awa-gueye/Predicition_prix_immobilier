"""
ImmoPredict SN — chatbot (Hugging Face Inference API)
Utilise l'endpoint /v1/chat/completions (compatible OpenAI) — plus fiable.
"""
import json, logging, os, re, time
import statistics as _st
from collections import defaultdict, Counter
import urllib.request, urllib.error
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# ── Modèles gratuits testés et fonctionnels ──────────────────
HF_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "HuggingFaceH4/zephyr-7b-beta",
    "microsoft/Phi-3-mini-4k-instruct",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "meta-llama/Meta-Llama-3-8B-Instruct",
]

# Nouvel endpoint unifié HF (compatible OpenAI chat completions)
HF_ENDPOINT = "https://api-inference.huggingface.co/v1/chat/completions"


# ── Contexte marché ───────────────────────────────────────────
def _build_context():
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
                flds  = [f for f in ["price","city","property_type"] if f in avail]
                for p in M.objects.filter(price__gte=500000).values(*flds)[:1500]:
                    data.append(p)
            except Exception:
                continue

        if not data:
            return ""

        prices = [float(d["price"]) for d in data if d.get("price")]
        if not prices:
            return ""

        types  = Counter(str(d.get("property_type","") or "").strip() for d in data)
        by_city = defaultdict(list)
        for d in data:
            c = str(d.get("city","") or "").strip().title()
            if c and c != "Inconnu":
                by_city[c].append(float(d["price"]))

        top = sorted(
            [(c, _st.median(ps), len(ps)) for c,ps in by_city.items() if len(ps)>=5],
            key=lambda x: x[1], reverse=True,
        )[:8]

        def fmt(p):
            if p>=1e9: return f"{p/1e9:.1f} Mds"
            if p>=1e6: return f"{p/1e6:.1f}M"
            if p>=1e3: return f"{p/1e3:.0f}K"
            return str(int(p))

        return (
            f"DONNÉES MARCHÉ SÉNÉGALAIS : {len(data):,} annonces | "
            f"Prix médian {fmt(_st.median(prices))} FCFA | "
            f"Fourchette {fmt(min(prices))}–{fmt(max(prices))} FCFA\n"
            "Types : " + ", ".join(f"{t}({n})" for t,n in types.most_common(5)) + "\n"
            "Quartiers : " + " | ".join(f"{c} {fmt(p)} FCFA" for c,p,n in top)
        )
    except Exception:
        return ""


# ── Prompt système ────────────────────────────────────────────
SYSTEM = (
    "Tu es ImmoAI, l'assistant intelligent de ImmoPredict SN, "
    "la première plateforme IA dédiée au marché immobilier sénégalais. "
    "Tu es polyvalent comme ChatGPT : tu réponds à TOUTES les questions "
    "(immobilier, culture générale, maths, histoire, cuisine, sport, code, etc.). "
    "Règles : réponds toujours en français, sois précis et structuré, "
    "ne refuse jamais de répondre, formate les prix en FCFA."
)


# ── Appel API ─────────────────────────────────────────────────
def _call_hf(question, history=None):
    api_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
    if not api_key:
        raise EnvironmentError("HUGGINGFACE_API_KEY non configurée")

    ctx = _build_context()
    system_msg = SYSTEM + (f"\n{ctx}" if ctx else "")

    # Construire les messages (format OpenAI)
    messages = [{"role": "system", "content": system_msg}]
    if history:
        for m in history[-8:]:
            role    = m.get("role","")
            content = m.get("content","").strip()
            if role in ("user","assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    errors = []
    for model in HF_MODELS:
        payload = json.dumps({
            "model":      model,
            "messages":   messages,
            "max_tokens": 800,
            "temperature": 0.7,
            "stream":     False,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                HF_ENDPOINT, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            text = (data.get("choices") or [{}])[0] \
                       .get("message", {}) \
                       .get("content", "").strip()
            if text:
                logger.info(f"ImmoAI: réponse via {model}")
                return text

        except urllib.error.HTTPError as e:
            code = e.code
            body = e.read().decode("utf-8", errors="ignore")
            err  = f"{model} → HTTP {code}: {body[:120]}"
            errors.append(err)
            logger.warning(err)

            if code == 401:
                raise EnvironmentError(
                    "Clé Hugging Face invalide. Vérifiez HUGGINGFACE_API_KEY."
                )
            if code == 429:
                time.sleep(1)       # petit délai avant le modèle suivant
            continue

        except Exception as e:
            err = f"{model} → {e}"
            errors.append(err)
            logger.warning(err)
            continue

    raise RuntimeError("Indisponible:\n" + "\n".join(errors))


# ── Nettoyage réponse ─────────────────────────────────────────
def _to_html(text):
    if not text:
        return ""
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>', text)
    text = re.sub(r'^#{1,3}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-•]\s+', '• ', text, flags=re.MULTILINE)
    text = text.replace('\n\n', '<br><br>').replace('\n', '<br>')
    text = re.sub(r'```\w*', '', text)
    return text.strip()


# ── Endpoint Django ───────────────────────────────────────────
@login_required(login_url="/immo/login/")
def api_chatbot(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST requis"}, status=405)

    try:
        body     = json.loads(request.body)
        question = body.get("message", "").strip()
        history  = body.get("history", [])

        if not question:
            return JsonResponse({"error": "Message vide"}, status=400)

        try:
            raw = _call_hf(question, history)
            return JsonResponse({
                "response":   _to_html(raw),
                "total":      0,
                "properties": [],
            })

        except EnvironmentError as e:
            return JsonResponse({
                "response": (
                    f"⚠️ {e}<br><br>"
                    "Ajoutez <b>HUGGINGFACE_API_KEY</b> dans les variables "
                    "d'environnement Render.<br>"
                    "Clé gratuite : "
                    "<a href='https://huggingface.co/settings/tokens' "
                    "target='_blank' style='color:#1A8ED8'>"
                    "huggingface.co/settings/tokens</a>"
                ),
                "total": 0, "properties": [],
            })

        except RuntimeError as e:
            logger.error(f"Tous modèles HF échoués: {e}")
            return JsonResponse({
                "response": (
                    "Les serveurs IA sont momentanément surchargés. "
                    "Réessayez dans quelques secondes."
                ),
                "total": 0, "properties": [],
            })

    except Exception as e:
        logger.error(f"Chatbot: {e}")
        return JsonResponse({
            "response": "Erreur. Réessayez.",
            "total": 0, "properties": [],
        })
