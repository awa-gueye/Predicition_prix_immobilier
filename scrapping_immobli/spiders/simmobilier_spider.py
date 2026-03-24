# -*- coding: utf-8 -*-
"""
Spider 2simmobilier.com — ImmoPredict SN
Extrait : titre, prix, type, ville, quartier, surface, chambres, SDB, description, images, URL
"""
import re
import scrapy
from scrapy.loader import ItemLoader
from itemloaders.processors import TakeFirst, MapCompose, Join
from urllib.parse import urljoin


def clean_price(text):
    """Nettoie et convertit un prix en float."""
    if not text:
        return None
    text = str(text).replace('\xa0', '').replace('\u202f', '').replace(' ', '')
    text = text.replace('FCFA', '').replace('CFA', '').replace('XOF', '')
    text = text.replace('.', '').replace(',', '.').strip()
    try:
        v = float(re.sub(r'[^\d.]', '', text))
        return v if v > 0 else None
    except:
        return None


def clean_int(text):
    if not text:
        return None
    try:
        return int(re.sub(r'[^\d]', '', str(text)))
    except:
        return None


def clean_text(text):
    if not text:
        return None
    return ' '.join(str(text).split()).strip()


class SimmobilierSpider(scrapy.Spider):
    name            = "simmobilier"
    allowed_domains = ["2simmobilier.com"]
    start_urls      = ["https://www.2simmobilier.com/annonces/"]

    custom_settings = {
        'DOWNLOAD_DELAY':           1.5,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS':      2,
        'ROBOTSTXT_OBEY':           True,
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'DEFAULT_REQUEST_HEADERS': {
            'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        },
        'ITEM_PIPELINES': {
            'scrapping_immobli.pipelines.SimmobilierPipeline': 300,
        },
    }

    # URLs de départ pour les différentes catégories
    CATEGORY_URLS = [
        "https://www.2simmobilier.com/annonces/?type=vente",
        "https://www.2simmobilier.com/annonces/?type=location",
        "https://www.2simmobilier.com/annonces/?type=vente&category=villa",
        "https://www.2simmobilier.com/annonces/?type=vente&category=appartement",
        "https://www.2simmobilier.com/annonces/?type=vente&category=terrain",
        "https://www.2simmobilier.com/annonces/?type=location&category=appartement",
    ]

    def start_requests(self):
        for url in self.CATEGORY_URLS:
            yield scrapy.Request(url, callback=self.parse_list)

    def parse_list(self, response):
        """Parse la liste des annonces."""
        # Sélecteurs adaptés à la structure de 2simmobilier.com
        # Les annonces sont typiquement dans des cards/articles
        annonces = response.css(
            'article.property-item, .listing-item, .property-card, '
            '.annonce-item, div[class*="property"], div[class*="listing"]'
        )

        if not annonces:
            # Fallback : chercher tous les liens vers des annonces individuelles
            annonces = response.css('a[href*="/annonce/"], a[href*="/property/"], a[href*="/bien/"]')

        for ann in annonces:
            # Extraire l'URL de l'annonce
            url = ann.css('a::attr(href), ::attr(href)').get('')
            if not url:
                continue
            url = urljoin(response.url, url)
            if '2simmobilier.com' in url:
                yield scrapy.Request(url, callback=self.parse_detail)

        # Pagination
        next_page = response.css(
            'a[rel="next"]::attr(href), .next a::attr(href), '
            'a.next::attr(href), .pagination .next::attr(href), '
            'li.next a::attr(href)'
        ).get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_list)

    def parse_detail(self, response):
        """Parse le détail d'une annonce."""
        item = {}

        item['url']   = response.url
        item['source'] = '2simmobilier'

        # ── Titre ──────────────────────────────────────────────────────────
        item['title'] = clean_text(response.css(
            'h1.property-title, h1.listing-title, h1.titre, h1[class*="title"], '
            '.property-name h1, h1::text, .annonce-titre::text'
        ).get(''))

        # ── Prix ───────────────────────────────────────────────────────────
        raw_price = response.css(
            '.property-price, .listing-price, .prix, [class*="price"], '
            '.annonce-prix, span[class*="price"]'
        ).css('::text').get('')

        if not raw_price:
            # Chercher dans le texte global
            raw_price = ' '.join(response.css('[class*="price"] ::text').getall())

        item['price'] = clean_price(raw_price)

        # ── Type de bien ───────────────────────────────────────────────────
        item['property_type'] = clean_text(response.css(
            '.property-type, .type-bien, [class*="type"], .categorie, '
            'span[class*="type"]::text, .bien-type::text'
        ).get('')) or self._extract_type_from_title(item.get('title',''))

        # ── Transaction (vente/location) ───────────────────────────────────
        item['statut'] = clean_text(response.css(
            '.transaction, .statut, [class*="transaction"], '
            '[class*="status"]::text, .vente-location::text'
        ).get('')) or self._extract_statut(response, item.get('price'))

        # ── Localisation ───────────────────────────────────────────────────
        location_text = ' '.join(response.css(
            '.property-location, .location, .ville, .quartier, '
            '[class*="location"], [class*="address"], .adresse, '
            '.localisation, span[class*="city"]'
        ).css('::text').getall())

        item['city']     = self._extract_city(location_text or response.css('title::text').get(''))
        item['district'] = self._extract_district(location_text)

        # ── Caractéristiques ───────────────────────────────────────────────
        # Surface
        surface_text = ' '.join(response.css(
            '[class*="surface"], [class*="area"], .superficie, '
            'span[class*="size"]'
        ).css('::text').getall())
        if not surface_text:
            surface_text = response.text
        item['surface_area'] = self._extract_number(surface_text, r'(\d+(?:[.,]\d+)?)\s*m[²2]')

        # Chambres
        bedrooms_text = ' '.join(response.css(
            '[class*="bedroom"], [class*="chambre"], .chambres, '
            'span[class*="room"]'
        ).css('::text').getall())
        if not bedrooms_text:
            bedrooms_text = response.text
        item['bedrooms']  = self._extract_int(bedrooms_text, r'(\d+)\s*(?:chambre|ch\b|pièce)')
        item['bathrooms'] = self._extract_int(response.text, r'(\d+)\s*(?:salle|bain|douche|sdb)')

        # Garage
        garage_text = response.text.lower()
        item['garage'] = 1 if any(w in garage_text for w in ['garage','parking','voiture']) else 0

        # ── Description ────────────────────────────────────────────────────
        item['description'] = clean_text(' '.join(response.css(
            '.property-description, .description, [class*="description"], '
            '.annonce-description, .detail-text, article p'
        ).css('::text').getall()[:500]))

        # ── Images ────────────────────────────────────────────────────────
        images = response.css(
            '.property-gallery img::attr(src), .gallery img::attr(src), '
            '[class*="gallery"] img::attr(src), .photos img::attr(src)'
        ).getall()
        item['images'] = [urljoin(response.url, img) for img in images[:5]] if images else []

        # ── Coordonnées GPS ────────────────────────────────────────────────
        # Chercher dans les scripts ou balises data
        lat = self._extract_from_scripts(response, r'lat[itude]*["\s:=]+([0-9.]+)')
        lon = self._extract_from_scripts(response, r'lon[gitude]*["\s:=]+(-?[0-9.]+)')
        item['latitude']  = float(lat) if lat and 12 < float(lat) < 17  else None
        item['longitude'] = float(lon) if lon and -18 < float(lon) < -14 else None

        # Validation minimale
        if item.get('title') and (item.get('price') or item.get('description')):
            yield item

    # ── Méthodes utilitaires ───────────────────────────────────────────────────

    def _extract_type_from_title(self, title):
        if not title: return 'Bien'
        tl = title.lower()
        types = [('Villa','villa'),('Appartement','appart'),('Terrain','terrain'),
                 ('Duplex','duplex'),('Studio','studio'),('Maison','maison'),
                 ('Local','local'),('Bureau','bureau')]
        for label, kw in types:
            if kw in tl: return label
        return 'Bien'

    def _extract_statut(self, response, price):
        full_text = response.text.lower()
        if any(w in full_text[:2000] for w in ['location','à louer','a louer','loyer']):
            return 'Location'
        if any(w in full_text[:2000] for w in ['vente','à vendre','a vendre','achat']):
            return 'Vente'
        # Heuristique par prix
        if price and price < 2_000_000:
            return 'Location'
        return 'Vente'

    def _extract_city(self, text):
        if not text: return 'Dakar'
        cities = [
            'Almadies','Ngor','Ouakam','Mermoz','Plateau','Fann','Yoff','Pikine',
            'Guédiawaye','Rufisque','Thiès','Mbour','Saly','Dakar','Sicap',
            'Grand Yoff','HLM','Liberté','Médina','Parcelles','VDN',
        ]
        tl = text.lower()
        for c in sorted(cities, key=len, reverse=True):
            if c.lower() in tl: return c
        return 'Dakar'

    def _extract_district(self, text):
        if not text: return None
        parts = [p.strip() for p in re.split(r'[,/|]', text) if p.strip()]
        return parts[-1] if parts else None

    def _extract_number(self, text, pattern):
        if not text: return None
        m = re.search(pattern, str(text), re.IGNORECASE)
        if m:
            try: return float(m.group(1).replace(',','.'))
            except: pass
        return None

    def _extract_int(self, text, pattern):
        if not text: return None
        m = re.search(pattern, str(text), re.IGNORECASE)
        if m:
            try: return int(m.group(1))
            except: pass
        return None

    def _extract_from_scripts(self, response, pattern):
        for script in response.css('script::text').getall():
            m = re.search(pattern, script, re.IGNORECASE)
            if m: return m.group(1)
        return None
