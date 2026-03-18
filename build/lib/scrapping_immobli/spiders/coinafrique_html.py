import scrapy
from scrapy.loader import ItemLoader
from scrapping_immobli.items import PropertyItem
import re
import json
from itemloaders.processors import MapCompose, TakeFirst


connection_string = "postgresql://neondb_owner:npg_ciyfh8H9bZdj@ep-frosty-wind-a4aoph5q-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

class CoinAfriqueHtmlSpider(scrapy.Spider):
    name = "coinafrique_html"
    allowed_domains = ["sn.coinafrique.com"]

    # ------------------------------------------------------------------
    # 1) POINT D’ENTRÉE : rubrique « VENTE » (évite location/chambres)
    # ------------------------------------------------------------------
    start_urls = ["https://sn.coinafrique.com/categorie/immobilier"]

    # ------------------------------------------------------------------
    # 2) CONFIGURATION
    # ------------------------------------------------------------------
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 16,
        "ROBOTSTXT_OBEY": False,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Referer": "https://sn.coinafrique.com",
        },
    }

    # ------------------------------------------------------------------
    # 3) PARSING DU LISTING
    # ------------------------------------------------------------------
    def parse(self, response):
        """
        Extrait tous les liens vers des annonces puis pagine.
        """
        for link in response.css('div.column.four-fifth a[href*="/annonce/"]'):
            yield response.follow(link, callback=self.parse_detail)
            print("Lien extrait :", link.get())

        # pagination
        next_link = response.css('li.pagination-indicator.direction a[href*="page="]::attr(href)').getall()[-1]
        if next_link:
            self.logger.info("Suivant : %s", next_link)
            yield response.follow(next_link, callback=self.parse)


    # ------------------------------------------------------------------
    # 4) PAGE DÉTAIL
    # ------------------------------------------------------------------
    def parse_detail(self, response):

        loader = ItemLoader(item=PropertyItem(), response=response)

        # Visible
        loader.add_css("title", "h1.title-ad::text")
        loader.add_css("price", "p.price::text")
        loader.add_css("city", "span[data-address] span::text")
        loader.add_css("description", "div.ad__info__box-descriptions p:nth-of-type(2)::text")

        def _int(txt):
            try:
                return int(re.sub(r'\D', '', txt.strip()))
            except (ValueError, AttributeError):
                return None

        def _float_m2(txt):
            try:
                return float(re.search(r'(\d+(?:\.\d+)?)', txt.replace('\u202f', '').replace(' ', '')).group(1))
            except (ValueError, AttributeError):
                return None

        # ------------------------------------------------------------------
        # Dans parse_detail
        # ------------------------------------------------------------------
        loader.add_css("bedrooms", "div.details-characteristics li:contains('pièces') span.qt::text",
                    MapCompose(str.strip, _int), TakeFirst())

        loader.add_css("bathrooms", "div.details-characteristics li:contains('salle') span.qt::text",
                    MapCompose(str.strip, _int), TakeFirst())

        loader.add_css("surface_area", "div.details-characteristics li:contains('Superficie') span.qt::text",
                    MapCompose(str.strip, _float_m2), TakeFirst())

        # Attributs
        geo = response.css("div#ad-details::attr(data-geolocation)").get()
        if geo:
            lat = re.search(r'"lat":([\d\.-]+)', geo)
            lng = re.search(r'"lng":([\d\.-]+)', geo)
            loader.add_value("latitude", lat.group(1) if lat else None)
            loader.add_value("longitude", lng.group(1) if lng else None)


        loader.add_value("url", response.url)
        loader.add_value("source", self.name)
        # --- Statut annonceur ---
        if response.css("a.card-image img.icon-pro"):
            statut = "Pro"
        else:
            statut = "Particulier"
        loader.add_value("statut", statut)

        # --- Nombre d'annonces ---
        nb_ads_text = response.css("p.nb-ads::text").get()
        if nb_ads_text:
            match = re.search(r"(\d+)", nb_ads_text)
            if match:
                loader.add_value("nb_annonces", int(match.group(1)))

        # Temps de publication
        try:
            posted_time = response.css("div.extra-info-ad-detail span.valign-wrapper span::text").get()
            if posted_time:
                loader.add_value("posted_time", posted_time.strip())
                self.logger.debug(f"[TIME] {posted_time}")
            else:
                self.logger.warning(f"[TIME] manquant sur {response.url}")
        except Exception as e:
            self.logger.error(f"[ERROR TIME] {e}")

        # Adresse
        try:
            adresse = response.css("div.extra-info-ad-detail span[data-address] span::text").get()
            if adresse:
                loader.add_value("adresse", adresse.strip())
                self.logger.debug(f"[ADRESSE] {adresse}")
            else:
                self.logger.warning(f"[ADRESSE] manquante sur {response.url}")
        except Exception as e:
            self.logger.error(f"[ERROR ADRESSE] {e}")

        # Type de bien
        try:
            property_type = response.css("div.extra-info-ad-detail span.valign-wrapper img + span::text").get()
            if property_type:
                loader.add_value("property_type", property_type.strip())
                self.logger.debug(f"[TYPE] {property_type}")
            else:
                self.logger.warning(f"[TYPE] manquant sur {response.url}")
        except Exception as e:
            self.logger.error(f"[ERROR TYPE] {e}")



        yield loader.load_item()