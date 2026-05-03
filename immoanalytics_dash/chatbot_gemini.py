"""
ImmoPredict SN — chatbot_hf.py (remplace chatbot_gemini.py)
Chatbot propulsé par Hugging Face Inference API.
Modèles gratuits avec fallback automatique.
"""
import re, json, logging, os, time
import statistics as _st
from collections import defaultdict, Counter
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Modèles Hugging Face gratuits (Inference API) — ordre de priorité
HF_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
    "microsoft/Phi-3-mini-4k-instruct",
]

HF_API_URL = "https://api-inference.huggingface.co/models/{model}"


# ══════════════════════════════════════════════════════════════
# CONTEXTE MARCHÉ
# ══════════════════════════════════════════════════════════════

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
                flds = [f for f in ["price", "city", "property_type"] if f in avail]
                for p in M.objects.filter(price__gte=500000).values(*flds)[:2000]:
                    data.append(p)
            except Exception:
                continue

        if not data:
            return ""

        prices = [float(d["price"]) for d in data if d.get("price")]
        if not prices:
            return ""

        types = Counter(str(d.get("property_type", "") or "").strip() for d in data)
        by_city = defaultdict(list)
        for d in data:
            c = str(d.get("city", "") or "").strip().title()
            if c and c not in ("Inconnu", ""):
                by_city[c].append(float(d["price"]))

        top = sorted(
            [(c, _st.median(ps), len(ps))
             for c, ps in by_city.items() if len(ps) >= 5],
            key=lambda x: x[1], reverse=True,
        )[:8]

        def fmt(p):
            if p >= 1e9: return f"{p/1e9:.1f} Mds"
            if p >= 1e6: return f"{p/1e6:.1f}M"
            if p >= 1e3: return f"{p/1e3:.0f}K"
            return str(int(p))

        return (
            f"DONNÉES RÉELLES DU MARCHÉ IMMOBILIER SÉNÉGALAIS :\n"
            f"• {len(data):,} annonces indexées\n"
            f"• Prix médian : {fmt(_st.median(prices))} FCFA\n"
            f"• Fourchette : {fmt(min(prices))} – {fmt(max(prices))} FCFA\n"
            "Types : " + ", ".join(f"{t} ({n})" for t, n in types.most_common(5)) + "\n"
            "Prix médians par quartier :\n"
            + "\n".join(f"• {c}: {fmt(p)} FCFA ({n} ann.)" for c, p, n in top)
            + "\nRepères : Villa Almadies 150–500M | Appt Mermoz 40–120M | "
              "Studio Plateau 10–35M | Terrain Pikine 3–25M FCFA"
        )
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
# PROMPT SYSTÈME
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Tu es ImmoAI, l'assistant intelligent de ImmoPredict SN, \
la première plateforme IA dédiée au marché immobilier sénégalais.
Tu es un assistant polyvalent. Tu réponds à TOUTES les questions sans exception : \
immobilier, culture générale, mathématiques, histoire, sciences, cuisine, sport, \
programmation, droit, santé, etc.
Règles : réponds toujours en français, sois précis et structuré, \
formate les prix en FCFA, ne refuse jamais de répondre, \
utilise les données du marché fournies pour les questions immobilières."""


def _build_prompt(question, history, context):
    """Construit le prompt au format instruction pour les LLMs."""
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n{context}"

    # Format conversationnel
    messages = []
    if history:
        for msg in history[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if role and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    # Format instruct universel (fonctionne avec Mistral, LLaMA, Zephyr)
    prompt = f"<s>[INST] <<SYS>>\n{system}\n<</SYS>>\n\n"

    # Ajouter l'historique
    for i, msg in enumerate(messages[:-1]):
        if msg["role"] == "user":
            if i == 0:
                prompt += f"{msg['content']} [/INST]"
            else:
                prompt += f"<s>[INST] {msg['content']} [/INST]"
        elif msg["role"] == "assistant":
            prompt += f" {msg['content']} </s>"

    # Question courante
    if len(messages) == 1:
        prompt += f"{question} [/INST]"
    else:
        prompt += f" <s>[INST] {question} [/INST]"

    return prompt


# ══════════════════════════════════════════════════════════════
# APPEL HUGGING FACE AVEC FALLBACK
# ══════════════════════════════════════════════════════════════

def _call_hf(question, history=None):
    """Appelle l'Inference API Hugging Face avec fallback sur plusieurs modèles."""
    import urllib.request
    import urllib.error

    api_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
    if not api_key:
        raise EnvironmentError("HUGGINGFACE_API_KEY non configurée")

    context = _build_context()
    prompt = _build_prompt(question, history, context)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = json.dumps({
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 800,
            "temperature": 0.7,
            "top_p": 0.9,
            "do_sample": True,
            "return_full_text": False,
            "stop": ["</s>", "[INST]", "<<SYS>>"],
        },
        "options": {
            "use_cache": False,
            "wait_for_model": True,   # Attend que le modèle charge (évite 503)
        },
    }).encode("utf-8")

    last_error = None
    for model in HF_MODELS:
        url = HF_API_URL.format(model=model)
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Extraire le texte généré
            if isinstance(result, list) and result:
                text = result[0].get("generated_text", "")
            elif isinstance(result, dict):
                text = result.get("generated_text", "")
                if not text and result.get("error"):
                    raise RuntimeError(result["error"])
            else:
                text = str(result)

            text = text.strip()
            if text:
                logger.info(f"HF: réponse via {model}")
                return text

        except urllib.error.HTTPError as e:
            code = e.code
            body = e.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {code}: {body[:100]}"

            if code == 429:
                logger.warning(f"Rate limit sur {model}")
                time.sleep(1)
                continue
            elif code in (503, 504):
                # Modèle en cours de chargement
                logger.warning(f"Modèle {model} en chargement (503/504)")
                time.sleep(2)
                continue
            elif code == 404:
                logger.warning(f"Modèle {model} non disponible")
                continue
            elif code == 401:
                raise EnvironmentError("Clé Hugging Face invalide. Vérifiez HUGGINGFACE_API_KEY.")
            else:
                logger.warning(f"Erreur {code} sur {model}: {body[:80]}")
                continue

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Erreur sur {model}: {e}")
            continue

    raise RuntimeError(f"Tous les modèles indisponibles. Dernière erreur : {last_error}")


def _clean_response(text):
    """Nettoie et formate la réponse en HTML."""
    if not text:
        return ""
    # Supprimer les artefacts de prompt qui peuvent rester
    for tag in ["[INST]", "[/INST]", "<<SYS>>", "<</SYS>>", "<s>", "</s>", "Assistant:", "ImmoAI:"]:
        text = text.replace(tag, "")
    text = text.strip()
    # Markdown → HTML
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'^#{1,3}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-•]\s+', '• ', text, flags=re.MULTILINE)
    text = text.replace('\n\n', '<br><br>').replace('\n', '<br>')
    text = re.sub(r'```[\w]*<br>', '<br>', text)
    text = re.sub(r'```', '', text)
    return text.strip()


# ══════════════════════════════════════════════════════════════
# ENDPOINT DJANGO
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

        try:
            raw = _call_hf(question, history)
            return JsonResponse({
                "response": _clean_response(raw),
                "total": 0,
                "properties": [],
            })

        except EnvironmentError as e:
            return JsonResponse({
                "response": (
                    f"Chatbot non configuré : <b>{e}</b><br><br>"
                    "Ajoutez <b>HUGGINGFACE_API_KEY</b> dans les variables "
                    "d'environnement Render.<br>"
                    "Clé gratuite sur "
                    "<a href='https://huggingface.co/settings/tokens' "
                    "target='_blank' style='color:#1A8ED8'>"
                    "huggingface.co/settings/tokens</a>"
                ),
                "total": 0, "properties": [],
            })

        except RuntimeError as e:
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
            "response": "Erreur temporaire. Réessayez.",
            "total": 0, "properties": [],
        })
