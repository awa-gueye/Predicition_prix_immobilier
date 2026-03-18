import scrapy
import hashlib
import re
from datetime import datetime

RE_DIGITS    = re.compile(r'[^\d]')
RE_PRIX_FR   = re.compile(r'([\d]{2,3}(?:\.[\d]{3})+)Fr')
RE_SURFACE   = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:m2|metres?\s*carres?|m\u00b2)', re.IGNORECASE)
RE_CITY      = re.compile(r'\b\u00e0\s+([A-Z\u00c0-\u00dca-z\u00e0-\u00ff][a-z\u00e0-\u00ff]+(?:[\s-][A-Z\u00c0-\u00dca-z\u00e0-\u00ff][a-z\u00e0-\u00ff]+)*)\s+S\u00e9n\u00e9gal', re.IGNORECASE)
RE_LAT       = re.compile(r'"lat(?:itude)?"\s*:\s*"?([-\d.]+)"?')
RE_LON       = re.compile(r'"l(?:ng|on)(?:gitude)?"\s*:\s*"?([-\d.]+)"?')


class ImmoSenegalSpider(scrapy.Spider):
    name = "immosenegal"
    allowed_domains = ["immobilier-au-senegal.com"]

    start_urls = [
        "https://immobilier-au-senegal.com/terrains-a-vendre/",
        "https://immobilier-au-senegal.com/villas-a-vendre/",
        "https://immobilier-au-senegal.com/locaux-commerciaux-a-vendre/",
        "https://immobilier-au-senegal.com/hotels/",
        "https://immobilier-au-senegal.com/auberges-a-vendre/",
        "https://immobilier-au-senegal.com/villas-a-louer/",
        "https://immobilier-au-senegal.com/appartements-a-louer/",
        "https://immobilier-au-senegal.com/duplex-a-louer/",
        "https://immobilier-au-senegal.com/location-longue-duree/",
        "https://immobilier-au-senegal.com/locaux-commerciaux/",
    ]

    custom_settings = {
        "ITEM_PIPELINES": {
            "scrapping_immobli.pipelines.ValidationPipeline":             100,
            "scrapping_immobli.pipelines.DuplicatesPipeline":             200,
            "scrapping_immobli.pipelines.ImmoSenegalPostgreSQLPipeline":  300,
        },
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 4,
        "ROBOTSTXT_OBEY": False,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
    }

    URL_MAP = {
        'terrains-a-vendre':           ('Terrain',           'vente'),
        'villas-a-vendre':             ('Villa',             'vente'),
        'locaux-commerciaux-a-vendre': ('Local commercial',  'vente'),
        'hotels':                      ('Hotel',             'vente'),
        'auberges-a-vendre':           ('Auberge',           'vente'),
        'villas-a-louer':              ('Villa',             'location'),
        'appartements-a-louer':        ('Appartement',       'location'),
        'duplex-a-louer':              ('Duplex',            'location'),
        'location-longue-duree':       ('Appartement',       'location'),
        'locaux-commerciaux':          ('Local commercial',  'location'),
    }

    def _get_type_transaction(self, url):
        for slug, (ptype, transaction) in self.URL_MAP.items():
            if slug in url:
                return ptype, transaction
        return None, None

    # ── PAGE LISTING ──────────────────────────────────────────────────────────

    def parse(self, response):
        property_type, transaction = self._get_type_transaction(response.url)
        links = list(set(response.css('a[href*="/bien/"]::attr(href)').getall()))
        self.logger.info("[IMMOSENEGAL] %d annonces sur %s", len(links), response.url)

        for link in links:
            yield response.follow(
                link, callback=self.parse_detail,
                meta={'property_type': property_type, 'transaction': transaction}
            )

        next_page = response.css('a.next.page-numbers::attr(href)').get()
        if next_page:
            yield response.follow(
                next_page, callback=self.parse,
                meta={'property_type': property_type, 'transaction': transaction}
            )

    # ── PAGE DÉTAIL ───────────────────────────────────────────────────────────

    def parse_detail(self, response):
        property_type = response.meta.get('property_type')
        transaction   = response.meta.get('transaction')

        # ── Titre ─────────────────────────────────────────────────────────────
        title = response.css('h1.page-title::text, h1::text').get('').strip()

        # ── Prix ──────────────────────────────────────────────────────────────
        # Le prix apparaît sous la forme "90.000.000Fr" (points = séparateurs de milliers)
        # On cherche tous les montants du format NNN.NNN.NNNFr et on prend le plus grand
        price = None

        # Méthode 1 : balises dédiées
        for sel in ['span.price::text', '.property-price::text', '.wre-price::text']:
            raw = response.css(sel).get('')
            if raw:
                digits = RE_DIGITS.sub('', raw)
                if digits and int(digits) >= 100000:
                    price = int(digits)
                    break

        # Méthode 2 : tous les montants XXX.XXX.XXXFr dans la page
        # On prend le maximum pour éviter les 1.000Fr du formulaire
        if not price:
            montants = RE_PRIX_FR.findall(response.text)
            if montants:
                valeurs = [int(RE_DIGITS.sub('', m)) for m in montants]
                candidat = max(valeurs)
                if candidat >= 100000:
                    price = candidat

        # ── Localisation ──────────────────────────────────────────────────────
        city = None

        city_raw = response.css('a[href*="/ville-bien/"]::text').get('')
        if city_raw:
            city = city_raw.strip().title()

        if not city:
            for txt in response.css('p::text, span::text').getall():
                txt = txt.strip()
                if 'negal,' in txt.lower():
                    parts = txt.split(',')
                    if len(parts) >= 2:
                        city = parts[-1].strip().title()
                        break

        if not city:
            m = RE_CITY.search(title)
            if m:
                city = m.group(1).strip().title()

        # ── Chambres, salles de bain, garage ──────────────────────────────────
        bedrooms  = None
        bathrooms = None
        garage    = None

        for li in response.css('li'):
            parts = li.css('::text').getall()
            raw   = ' '.join(p.strip() for p in parts).lower()
            nums  = [p.strip() for p in parts if p.strip().isdigit()]
            val   = int(nums[0]) if nums else None
            if not val:
                continue
            if 'chambre' in raw:
                bedrooms = val
            elif 'salle' in raw:
                bathrooms = val
            elif 'garage' in raw:
                garage = val

        # ── Superficie ────────────────────────────────────────────────────────
        surface_area = None

        m = RE_SURFACE.search(title)
        if m:
            try:
                surface_area = float(m.group(1).replace(',', '.'))
            except ValueError:
                pass

        if not surface_area:
            desc_raw = ' '.join(response.css(
                '.property-description *::text, #property-description *::text'
            ).getall())
            m = RE_SURFACE.search(desc_raw)
            if m:
                try:
                    surface_area = float(m.group(1).replace(',', '.'))
                except ValueError:
                    pass

        # ── Description ───────────────────────────────────────────────────────
        desc_parts = response.css(
            '.property-description *::text, '
            '#property-description *::text, '
            'div.description *::text'
        ).getall()
        description = ' '.join(d.strip() for d in desc_parts if d.strip()) or None

        # ── Coordonnées GPS ───────────────────────────────────────────────────
        latitude  = None
        longitude = None
        m_lat = RE_LAT.search(response.text)
        m_lon = RE_LON.search(response.text)
        if m_lat and m_lon:
            try:
                lat, lon = float(m_lat.group(1)), float(m_lon.group(1))
                if 10 < lat < 18 and -18 < lon < -10:
                    latitude, longitude = lat, lon
            except ValueError:
                pass

        self.logger.info("[IMMOSENEGAL] %s | prix=%s | ville=%s",
                         title[:50], price, city)

        yield {
            'id':            hashlib.md5(response.url.encode()).hexdigest(),
            'url':           response.url,
            'title':         title or None,
            'price':         price,
            'surface_area':  surface_area,
            'bedrooms':      bedrooms,
            'bathrooms':     bathrooms,
            'garage':        garage,
            'city':          city,
            'adresse':       city,
            'property_type': property_type,
            'transaction':   transaction,
            'description':   description,
            'source':        self.name,
            'statut':        'Pro',
            'latitude':      latitude,
            'longitude':     longitude,
            'scraped_at':    datetime.utcnow(),
        }