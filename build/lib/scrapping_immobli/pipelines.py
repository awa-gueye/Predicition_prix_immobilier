import psycopg2
import hashlib
import re
from datetime import datetime
from scrapy.exceptions import DropItem

def clean_list(value):
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    return str(value).strip() if value else None

def clean_int(value):
    try:
        return int(re.sub(r'\D', '', str(value).strip()))
    except (ValueError, AttributeError):
        return None

def clean_float(value):
    try:
        return float(re.search(r'(\d+(?:\.\d+)?)', str(value).replace('\u202f', '').replace(' ', '')).group(1))
    except (ValueError, AttributeError):
        return None

class ValidationPipeline:
    def process_item(self, item, spider):
        if not item.get("price"):
            raise DropItem("prix manquant")
        item["scraped_at"] = datetime.utcnow()
        return item

class DuplicatesPipeline:
    def __init__(self):
        self.urls_seen = set()

    def process_item(self, item, spider):
        url_hash = hashlib.md5(item["url"].encode()).hexdigest()
        if url_hash in self.urls_seen:
            raise DropItem(f"URL déjà traitée : {item['url']}")
        self.urls_seen.add(url_hash)
        item["id"] = url_hash
        return item

class PostgreSQLPipeline:
    def __init__(self, **db_params):
        self.db_params = db_params
        self.conn = None  # Initialisation pour éviter AttributeError

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings["DATABASE"])

    def open_spider(self, spider):
        self.conn = psycopg2.connect(**self.db_params)
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS properties(
                    id VARCHAR(32) PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    price INTEGER,
                    surface_area REAL,
                    bedrooms INTEGER,
                    bathrooms INTEGER,
                    city VARCHAR(100),
                    description TEXT,
                    source VARCHAR(50),
                    latitude REAL,
                    longitude REAL,
                    scraped_at TIMESTAMP,
                    statut VARCHAR(50),
                    nb_annonces INTEGER,
                    posted_time VARCHAR(100),
                    adresse VARCHAR(100),
                    property_type VARCHAR(100)
                );
            """)
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn and not self.conn.closed:
            try:
                self.conn.close()
                spider.logger.info("[POSTGRES] Connexion fermée proprement")
            except Exception as exc:
                spider.logger.warning("[POSTGRES] Erreur à la fermeture : %s", exc)

    def process_item(self, item, spider):
        spider.logger.info("[POSTGRES] INSERT %s", item["url"])
        item["bedrooms"]     = clean_int(item.get("bedrooms"))
        item["bathrooms"]    = clean_int(item.get("bathrooms"))
        item["surface_area"] = clean_float(item.get("surface_area"))
        item["posted_time"]  = clean_list(item.get("posted_time"))
        item["adresse"]      = clean_list(item.get("adresse"))
        item["property_type"]= clean_list(item.get("property_type"))
        item["statut"]       = clean_list(item.get("statut"))
        item["nb_annonces"]  = clean_list(item.get("nb_annonces"))

        try:
            optional_fields = ["status", "nb_annonces"]
            for field in optional_fields:
                value = item.get(field)
                if isinstance(value, list):
                    item[field] = value[0] 
                
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO properties(
                        id, url, title, price, city, description, source,
                        latitude, longitude, scraped_at,
                        bedrooms, bathrooms, surface_area,
                        posted_time, adresse, property_type, statut, nb_annonces
                    )
                    VALUES (
                        %(id)s, %(url)s, %(title)s, %(price)s,
                        %(city)s, %(description)s, %(source)s,
                        %(latitude)s, %(longitude)s, %(scraped_at)s,
                        %(bedrooms)s, %(bathrooms)s, %(surface_area)s,
                        %(posted_time)s, %(adresse)s, %(property_type)s,
                        %(statut)s, %(nb_annonces)s
                    )
                    ON CONFLICT (url) DO UPDATE SET
                        price = EXCLUDED.price,
                        scraped_at = EXCLUDED.scraped_at;
                """, dict(item))
            self.conn.commit()
            spider.logger.info("[POSTGRES] COMMIT %s", item["url"])
        except Exception as exc:
            self.conn.rollback()
            spider.logger.error("[POSTGRES] ERREUR %s : %s", item["url"], exc)
            raise
        return item

class ExpatDakarPostgreSQLPipeline:
    def __init__(self, **db_params):
        self.db_params = db_params
        self.conn = None  # Initialisation pour éviter AttributeError

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings["DATABASE"])

    def open_spider(self, spider):
        self.conn = psycopg2.connect(**self.db_params)
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS expat_dakar_properties(
                    id VARCHAR(32) PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    price INTEGER,
                    surface_area REAL,
                    bedrooms INTEGER,
                    bathrooms INTEGER,
                    city VARCHAR(100),
                    region VARCHAR(100),
                    description TEXT,
                    source VARCHAR(50),
                    scraped_at TIMESTAMP,
                    statut VARCHAR(50),
                    posted_time VARCHAR(100),
                    adresse VARCHAR(100),
                    property_type VARCHAR(100),
                    member_since VARCHAR(50)
                );
            """)
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn and not self.conn.closed:
            try:
                self.conn.close()
                spider.logger.info("[POSTGRES-EXPAT] Connexion fermée proprement")
            except Exception as exc:
                spider.logger.warning("[POSTGRES-EXPAT] Erreur à la fermeture : %s", exc)

    def process_item(self, item, spider):
        spider.logger.info("[POSTGRES-EXPAT] INSERT %s", item["url"])
        item["url"]          = clean_list(item.get("url"))
        item["bedrooms"]      = clean_int(item.get("bedrooms"))
        item["bathrooms"]     = clean_int(item.get("bathrooms"))
        item["surface_area"]  = clean_float(item.get("surface_area"))
        item["posted_time"]   = clean_list(item.get("posted_time"))
        item["adresse"]       = clean_list(item.get("adresse"))
        item["property_type"] = clean_list(item.get("property_type"))
        item["statut"]        = clean_list(item.get("statut"))
        item["member_since"]  = clean_list(item.get("member_since"))

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO expat_dakar_properties(
                        id, url, title, price, city, region, description, source,
                        scraped_at, bedrooms, bathrooms, surface_area,
                        posted_time, adresse, property_type, statut, member_since
                    )
                    VALUES (
                        %(id)s, %(url)s, %(title)s, %(price)s,
                        %(city)s, %(region)s, %(description)s, %(source)s,
                        %(scraped_at)s, %(bedrooms)s, %(bathrooms)s, %(surface_area)s,
                        %(posted_time)s, %(adresse)s, %(property_type)s,
                        %(statut)s, %(member_since)s
                    )
                    ON CONFLICT (url) DO UPDATE SET
                        price = EXCLUDED.price,
                        scraped_at = EXCLUDED.scraped_at;
                """, dict(item))
            self.conn.commit()
            spider.logger.info("[POSTGRES-EXPAT] COMMIT %s", item["url"])
        except Exception as exc:
            self.conn.rollback()
            spider.logger.error("[POSTGRES-EXPAT] ERREUR %s : %s", item["url"], exc)
            raise
        return item

class LogerDakarPostgreSQLPipeline:
    def __init__(self, **db_params):
        self.db_params = db_params
        self.conn = None  # Initialisation pour éviter AttributeError

    @classmethod
    def from_crawler(cls, crawler):
        return cls(**crawler.settings["DATABASE"])

    def open_spider(self, spider):
        self.conn = psycopg2.connect(**self.db_params)
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS loger_dakar_properties(
                    id VARCHAR(32) PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    price INTEGER,
                    surface_area REAL,
                    bedrooms INTEGER,
                    bathrooms INTEGER,
                    city VARCHAR(100),
                    region VARCHAR(100),
                    description TEXT,
                    source VARCHAR(50),
                    scraped_at TIMESTAMP,
                    statut VARCHAR(50),
                    posted_time VARCHAR(100),
                    adresse VARCHAR(100),
                    property_type VARCHAR(100),
                    listing_id VARCHAR(50)
                );
            """)
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def process_item(self, item, spider):
        item["url"]          = clean_list(item.get("url"))
        item["bedrooms"]     = clean_int(item.get("bedrooms"))
        item["bathrooms"]    = clean_int(item.get("bathrooms"))
        item["surface_area"] = clean_float(item.get("surface_area"))
        item["posted_time"]  = clean_list(item.get("posted_time"))
        item["adresse"]      = clean_list(item.get("adresse"))
        item["property_type"]= clean_list(item.get("property_type"))
        item["statut"]       = clean_list(item.get("statut"))
        item["listing_id"]   = clean_list(item.get("listing_id"))

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO loger_dakar_properties(
                        id, url, title, price, city, region, description, source,
                        scraped_at, bedrooms, bathrooms, surface_area,
                        posted_time, adresse, property_type, statut, listing_id
                    )
                    VALUES (
                        %(id)s, %(url)s, %(title)s, %(price)s,
                        %(city)s, %(region)s, %(description)s, %(source)s,
                        %(scraped_at)s, %(bedrooms)s, %(bathrooms)s, %(surface_area)s,
                        %(posted_time)s, %(adresse)s, %(property_type)s,
                        %(statut)s, %(listing_id)s
                    )
                    ON CONFLICT (url) DO UPDATE SET
                        price = EXCLUDED.price,
                        scraped_at = EXCLUDED.scraped_at;
                """, dict(item))
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            spider.logger.error("[POSTGRES-LOGER] ERREUR %s : %s", item["url"], exc)
            raise
        return item