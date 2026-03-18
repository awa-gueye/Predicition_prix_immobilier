import scrapy, re
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose, TakeFirst
from scrapping_immobli.items import ExpatDakarPropertyItem 




class ExpatDakarSpider(scrapy.Spider):
    name = "expat_dakar"
    allowed_domains = ["www.expat-dakar.com"]
    start_urls = ["https://www.expat-dakar.com/immobilier"]

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
            "Referer": "https://www.expat-dakar.com",
        },
        
    }

    # ------------------------------------------------------------------
    # 1) PAGE LISTING : extrait les liens vers les fiches + pagination
    # ------------------------------------------------------------------
    def parse(self, response):
        # 1.1 Extraire toutes les fiches
        for link in response.css('a.listing-card__inner[href*="/annonce/"]::attr(href)').getall():
            yield response.follow(link, callback=self.parse_detail)

        # 1.2 Pagination : bouton "Suivant"
        next_page = response.css('a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    # ------------------------------------------------------------------
    # 2) PAGE DÉTAIL : extraction complète
    # ------------------------------------------------------------------
    def parse_detail(self, response):
        loader = ItemLoader(item=ExpatDakarPropertyItem(), response=response)

        loader.add_css("title", "h1.listing-item__header::text")
        loader.add_css("price", "span.listing-card__price__value::text")
        loader.add_css("city", "span.listing-item__address-location::text")
        loader.add_css("region", "span.listing-item__address-region::text")
        loader.add_css("description", "div.listing-item__description *::text")

        def _int(txt):
            try:
                return int(re.sub(r"\D", "", txt.strip()))
            except (ValueError, AttributeError):
                return None

        def _float_m2(txt):
            try:
                return float(
                    re.search(r"(\d+(?:\.\d+)?)", txt.replace("\u202f", "").replace(" ", "")).group(1)
                )
            except (ValueError, AttributeError):
                return None

        loader.add_css("bedrooms", "dt:contains('Chambres') + dd::text",
                       MapCompose(str.strip, _int), TakeFirst())
        loader.add_css("bathrooms", "dt:contains('Salle de Bain') + dd::text",
                       MapCompose(str.strip, _int), TakeFirst())
        loader.add_css("surface_area", "dt:contains('Mètres carrés') + dd::text",
                       MapCompose(str.strip, _float_m2), TakeFirst())

        loader.add_value("url", response.url)
        loader.add_value("source", self.name)
        loader.add_value("statut", "Particulier")

        loader.add_css("listing_id", "div.listing-item__details__ad-id::text",
                       MapCompose(lambda x: x.replace("Référence de l'annonce :", "").strip()))
        loader.add_css("posted_time", "div.listing-item__details__date::text", MapCompose(str.strip))
        loader.add_value("property_type", "Appartement")
        loader.add_css(
                "member_since",
                "span.listing-item-transparency__member-since::text",
                MapCompose(lambda x: x.replace("Membre depuis", "").strip())
            )
        yield loader.load_item()
