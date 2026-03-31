"""
properties/management/commands/run_scrapers.py
Commande Django pour lancer les scrapers en continu.
Usage: python manage.py run_scrapers --interval 3600
"""
import time
import subprocess
import os
import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Lance les scrapers Scrapy en continu avec un intervalle défini'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=3600,
            help='Intervalle en secondes entre chaque cycle (défaut: 3600 = 1h)',
        )
        parser.add_argument(
            '--spiders',
            nargs='+',
            default=['coinafrique_html', 'expat_dakar', 'loger_dakar', 'dakarvente'],
            help='Liste des spiders à lancer',
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Lancer une seule fois sans boucle',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        spiders  = options['spiders']
        once     = options['once']

        # Trouver le répertoire du projet Scrapy
        base_dir   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))))
        scrapy_dir = os.path.join(base_dir, 'scrapping_immobli')

        if not os.path.exists(scrapy_dir):
            self.stderr.write(f"Répertoire Scrapy introuvable: {scrapy_dir}")
            return

        self.stdout.write(self.style.SUCCESS(
            f"Démarrage collecte continue — {len(spiders)} spiders, intervalle {interval}s"))

        cycle = 0
        while True:
            cycle += 1
            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"Cycle {cycle} — {time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.stdout.write('='*50)

            for spider in spiders:
                self.stdout.write(f"  → Lancement {spider}...")
                try:
                    result = subprocess.run(
                        ['scrapy', 'crawl', spider],
                        cwd=scrapy_dir,
                        capture_output=True,
                        text=True,
                        timeout=1800,  # 30 min max par spider
                    )
                    if result.returncode == 0:
                        self.stdout.write(self.style.SUCCESS(f"  ✅ {spider} OK"))
                    else:
                        self.stderr.write(f"  ❌ {spider} erreur: {result.stderr[-200:]}")
                except subprocess.TimeoutExpired:
                    self.stderr.write(f"  ⏱️ {spider} timeout (30min)")
                except Exception as e:
                    self.stderr.write(f"  ❌ {spider}: {e}")

            self.stdout.write(self.style.SUCCESS(
                f"\nCycle {cycle} terminé. Prochain dans {interval}s..."))

            if once:
                break

            time.sleep(interval)
