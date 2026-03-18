import scrapy
import hashlib
import re
from datetime import datetime


class DakarVenteSpider(scrapy.Spider):
    name = "dakarvente"
    allowed_domains = ["www.dakarvente.com"]
    start_urls = ["https://www.dakarvente.com/fr/annonces/immobilier"]

    custom_settings = {
        "ITEM_PIPELINES": {
            "scrapping_immobli.pipelines.ValidationPipeline":              100,
            "scrapping_immobli.pipelines.DuplicatesPipeline":              200,
            "scrapping_immobli.pipelines.DakarVentePostgreSQLPipeline":    300,
        },
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS": 8,
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

    # ─── PAGE LISTING ─────────────────────────────────────────────────────────

    def parse(self, response):
        links = list(set(response.css('a[href*="/fr/annonce/"]::attr(href)').getall()))
        self.logger.info(f"[DAKARVENTE] {len(links)} annonces sur {response.url}")

        for link in links:
            yield response.follow(link, callback=self.parse_detail)

        # Pagination
        match = re.search(r'[?&]page=(\d+)', response.url)
        current_page = int(match.group(1)) if match else 1
        sep = '&' if '?' in response.url else '?'
        if match:
            next_url = re.sub(r'page=\d+', f'page={current_page + 1}', response.url)
        else:
            next_url = f"{response.url}{sep}page={current_page + 1}"

        yield response.follow(next_url, callback=self.parse)

    # ─── PAGE DÉTAIL ──────────────────────────────────────────────────────────

    def parse_detail(self, response):

        def to_int(txt):
            if not txt:
                return None
            digits = re.sub(r'\D', '', str(txt).replace('\u202f','').replace('\xa0',''))
            return int(digits) if digits else None

        def to_float(txt):
            if not txt:
                return None
            try:
                m = re.search(r'(\d+(?:[.,]\d+)?)',
                              str(txt).replace('\u202f','').replace('\xa0',''))
                return float(m.group(1).replace(',','.')) if m else None
            except (AttributeError, ValueError):
                return None

        # ── Titre ─────────────────────────────────────────────────────────────
        title = response.css('h5::text').get('').strip()

        # ── Prix ──────────────────────────────────────────────────────────────
        price = None
        for txt in response.css('h2::text').getall():
            p = to_int(txt)
            if p and p > 0:
                price = p
                break

        # ── City et property_type — depuis les liens /fr/annonces/ ────────────
        # Structure breadcrumb observée :
        # <a href="/fr/accueil">Accueil</a> /
        # <a href="/fr/annonces">Annonces</a> /
        # <a href="/fr/annonces/appartements-louer">Appartements à louer</a> /
        # <a href="/fr/annonces/appartements-louer/mermoz">Mermoz</a>
        #
        # On collecte tous les href /fr/annonces/ et on classe par nb de segments

        property_type = None
        city = None

        for a in response.css('a[href*="/fr/annonces/"]'):
            href = a.attrib.get('href','').replace('https://www.dakarvente.com','')
            text = a.css('::text').get('').strip()
            if not text or not href:
                continue

            # Segments après /fr/annonces/
            after = href.replace('/fr/annonces/','').strip('/')
            segments = [s for s in after.split('/') if s]

            # Exclure les liens du menu principal
            MENU_SLUGS = {'immobilier','emploi','vehicules','multimedia',
                          'maison','boutiques','all','voitures','motos'}
            if not segments or segments[0] in MENU_SLUGS:
                continue

            if len(segments) == 1:
                # ex: /fr/annonces/appartements-louer -> property_type
                property_type = text
            elif len(segments) == 2:
                # ex: /fr/annonces/appartements-louer/mermoz -> city
                city = text

        # ── Caractéristiques — regex sur texte de la section Details ──────────
        # On isole le bloc entre "Details" et "Description" pour éviter le bruit
        full_text = ' '.join(response.css('*::text').getall())

        surface_area = None
        bedrooms     = None
        bathrooms    = None

        m = re.search(r'[Ss]uperficie\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*[Mm]', full_text)
        if m:
            surface_area = to_float(m.group(1))

        m = re.search(r'[Nn]ombre\s+de\s+pi[èe]ces?\s*[:\-]?\s*(\d+)', full_text)
        if m:
            bedrooms = int(m.group(1))

        m = re.search(r'[Nn]ombre\s+de\s+salles?\s+de\s+bains?\s*[:\-]?\s*(\d+)', full_text)
        if m:
            bathrooms = int(m.group(1))

        # ── Description — chercher le bloc après le h4 "Description" ──────────
        # On utilise XPath pour cibler le texte qui suit immédiatement le h4
        description = None

        # Méthode 1 : texte qui suit le heading "Description"
        desc_block = response.xpath(
            '//h4[contains(text(),"Description")]/following-sibling::*[1]//text() | '
            '//h5[contains(text(),"Description")]/following-sibling::*[1]//text()'
        ).getall()
        if desc_block:
            description = ' '.join(d.strip() for d in desc_block if d.strip())

        # Méthode 2 : fallback — paragraphe le plus long hors bruit
        if not description or len(description) < 20:
            NOISE = ('cookie', 'S\'inscrire', 'Connexion', 'DakarVente est',
                     'Restez informer', 'Conseils de sécurité', 'newsletter',
                     'Laisser un commentaire', 'Nos rubriques')
            candidates = []
            for p in response.css('p'):
                txt = ' '.join(p.css('::text').getall()).strip()
                if len(txt) > 50 and not any(n.lower() in txt.lower() for n in NOISE):
                    candidates.append(txt)
            description = max(candidates, key=len) if candidates else None

        # ── Statut Pro / Particulier ───────────────────────────────────────────
        has_boutique = bool(response.css('a[href*="/fr/boutique/"]').get())
        statut = 'Pro' if has_boutique else 'Particulier'

        yield {
            'id':            hashlib.md5(response.url.encode()).hexdigest(),
            'url':           response.url,
            'title':         title or None,
            'price':         price,
            'surface_area':  surface_area,
            'bedrooms':      bedrooms,
            'bathrooms':     bathrooms,
            'city':          city,
            'adresse':       city,
            'property_type': property_type,
            'description':   description,
            'source':        self.name,
            'statut':        statut,
            'latitude':      None,
            'longitude':     None,
            'scraped_at':    datetime.utcnow(),
        }