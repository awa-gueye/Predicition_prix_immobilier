import scrapy, re
from scrapy.loader import ItemLoader
from scrapping_immobli.items import ExpatDakarPropertyItem
from itemloaders.processors import MapCompose, TakeFirst



def extract_first_digit(text):
    if not text:
        return None
    m = re.search(r'\d+', text.strip())
    return int(m.group(0)) if m else None


class LogerDakarSpider(scrapy.Spider):
    name = "loger_dakar"
    allowed_domains = ["www.loger-dakar.com"]
    start_urls = ["https://www.loger-dakar.com/Bien/"]

    custom_settings = {
        "ITEM_PIPELINES": {
            "scrapping_immobli.pipelines.ValidationPipeline": 300,
            "scrapping_immobli.pipelines.DuplicatesPipeline": 400,
            "scrapping_immobli.pipelines.LogerDakarPostgreSQLPipeline": 900,
        },
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
            "Referer": "https://www.loger-dakar.com",
        },
    }

    # ------------------------------------------------------------------
    # 1) LISTING : toutes les fiches + pagination
    # ------------------------------------------------------------------
    def parse(self, response):
        # ✅ Vignettes d’annonces (vignette = <article> complet)
        for article in response.css('article.g5ere__property-item'):
            href = article.css('a.g5core__entry-thumbnail::attr(href)').get()
            title = article.css('a.g5core__entry-thumbnail::attr(title)').get()
            if href:
                yield response.follow(
                    href,
                    callback=self.parse_detail,
                    meta={"title": title}
                )

        # ✅ Pagination : bouton « Suivant »
        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    # ------------------------------------------------------------------
    # 2) DETAIL
    # ------------------------------------------------------------------
    def parse_detail(self, response):
        loader = ItemLoader(item=ExpatDakarPropertyItem(), response=response)

        loader.add_value("title", response.meta.get("title"))
        loader.add_css("price", "span.g5ere__lpp-price::text")
        loader.add_css("adresse", "li.address span::text", TakeFirst())
        loader.add_css("city", "li.city a::text", TakeFirst())
        loader.add_css("region", "li.state a::text", TakeFirst())
        loader.add_css("description", "div.g5ere__property-block-description *::text")

        # Chiffres
        loader.add_css("bedrooms", "span.g5ere__property-bedrooms::text", MapCompose(str.strip, extract_first_digit), TakeFirst())
        loader.add_css("bathrooms", "span.g5ere__property-bathrooms::text", MapCompose(str.strip, extract_first_digit), TakeFirst())
        loader.add_css("surface_area", "span.g5ere__loop-property-size::text",
                       MapCompose(lambda x: re.search(r'(\d+)', x).group(1) if x else None, float))

        # IDs & types
        loader.add_css("listing_id", "span.g5ere__property-identity::text")
        loader.add_css("posted_time", "div.g5ere__property-date span::text")
        loader.add_css("property_type", "span.g5ere__property-type a::text")
        loader.add_css("statut", "span.g5ere__property-status a::text")

        loader.add_value("url", response.url)
        loader.add_value("source", self.name)
        loader.add_value("member_since", None)  # pas dispo

        yield loader.load_item()