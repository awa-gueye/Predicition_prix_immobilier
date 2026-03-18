"""
Script de scraping automatique — à lancer chaque nuit à 2h.
Lance tous les spiders séquentiellement et enregistre les logs.

Usage manuel    : python scrape_scheduler.py
Planificateur   : configuré via Windows Task Scheduler
"""

import subprocess
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
# Chemin absolu vers le dossier du projet (à adapter)
PROJECT_DIR = Path(__file__).parent.resolve()
LOGS_DIR    = PROJECT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Chemin vers python dans le virtualenv
PYTHON = str(PROJECT_DIR / "env" / "Scripts" / "python.exe")
if not Path(PYTHON).exists():
    PYTHON = sys.executable  # fallback : python courant

# Spiders à lancer dans l'ordre
SPIDERS = [
    "coinafrique_html",
    "expat_dakar",
    "loger_dakar",
    "dakarvente",
    "immosenegal",
]

# ── Logging ───────────────────────────────────────────────────────────────────
log_file = LOGS_DIR / f"scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def run_spider(spider_name: str) -> bool:
    """Lance un spider Scrapy et retourne True si succès."""
    logger.info(f"{'='*50}")
    logger.info(f"Lancement du spider : {spider_name}")
    logger.info(f"{'='*50}")

    log_filename = LOGS_DIR / f"{spider_name}_{datetime.now().strftime('%Y%m%d')}.log"
    cmd = [PYTHON, "-m", "scrapy", "crawl", spider_name,
        "-L", "INFO",
        f"--logfile={log_filename}"]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_DIR),
            capture_output=False,
            timeout=3 * 3600,  # Timeout 3h par spider
        )
        if result.returncode == 0:
            logger.info(f"✅ {spider_name} terminé avec succès")
            return True
        else:
            logger.error(f"❌ {spider_name} a échoué (code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ {spider_name} timeout après 3h")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur inattendue pour {spider_name} : {e}")
        return False


def main():
    start = datetime.now()
    logger.info(f"{'#'*55}")
    logger.info(f"SCRAPING AUTOMATIQUE DÉMARRÉ — {start.strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info(f"{'#'*55}")
    logger.info(f"Spiders à lancer : {', '.join(SPIDERS)}")
    logger.info(f"Logs : {log_file}")

    results = {}
    for spider in SPIDERS:
        results[spider] = run_spider(spider)

    # Résumé
    elapsed = datetime.now() - start
    logger.info(f"\n{'#'*55}")
    logger.info(f"RÉSUMÉ — Durée totale : {elapsed}")
    logger.info(f"{'#'*55}")
    for spider, ok in results.items():
        status = "✅ OK" if ok else "❌ ÉCHEC"
        logger.info(f"  {spider:<25} : {status}")

    n_ok   = sum(results.values())
    n_fail = len(results) - n_ok
    logger.info(f"\n  Succès : {n_ok} / {len(results)} | Échecs : {n_fail}")

    if n_fail > 0:
        logger.warning("⚠️ Certains spiders ont échoué — vérifier les logs.")
        sys.exit(1)
    else:
        logger.info("🎉 Tous les spiders ont tourné avec succès !")


if __name__ == "__main__":
    main()