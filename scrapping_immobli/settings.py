import scrapy
from urllib.parse import urlparse, parse_qs
import os

BOT_NAME = "scrapping_immobli"

SPIDER_MODULES = ["scrapping_immobli.spiders"]
NEWSPIDER_MODULE = "scrapping_immobli.spiders"

# --- Configuration Scrapy ---
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_TARGET_CONCURRENCY = 8
FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
TELNETCONSOLE_ENABLED = False

# --- User-Agent rotatif ---
USER_AGENT_LIST = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

DOWNLOADER_MIDDLEWARES = {
    "scrapping_immobli.middlewares.RotateUserAgentMiddleware": 400,
}

# --- PostgreSQL Neon ---
NEON_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_4nOWqTAk0RCF@ep-lively-shape-anjt1g2k-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# Parse l'URL
parsed = urlparse(NEON_DATABASE_URL)
query_params = parse_qs(parsed.query)

# Construire le dictionnaire pour psycopg2
DATABASE = {
    "dbname": parsed.path.strip('/'),  # IMPORTANT : 'dbname' et pas 'database'
    "user": parsed.username,
    "password": parsed.password,
    "host": parsed.hostname,
    "port": parsed.port or 5432,
}

# Ajouter les paramètres SSL en extrayant les valeurs des listes
for key, value in query_params.items():
    DATABASE[key] = value[0]  # Prend le premier élément de la liste

# --- Pipelines ---
ITEM_PIPELINES = {
    "scrapping_immobli.pipelines.ValidationPipeline": 100,
    "scrapping_immobli.pipelines.DuplicatesPipeline": 200,
    
    # DÉCOMMENTEZ le bon pipeline selon votre spider :
    
    # Pour spider principal (table 'properties'):
    "scrapping_immobli.pipelines.CoinsafriquePostgreSQLPipeline": 300,
    
    # Pour ExpatDakar (table 'expat_dakar_properties'):
    #"scrapping_immobli.pipelines.ExpatDakarPostgreSQLPipeline": 300,
    
    # Pour LogerDakar (table 'loger_dakar_properties'):
    #"scrapping_immobli.pipelines.LogerDakarPostgreSQLPipeline": 300,
}