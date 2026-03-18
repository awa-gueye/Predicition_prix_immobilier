import scrapy
from itemloaders.processors import MapCompose, TakeFirst
import re
def _int(txt):
    if not txt:
        return None
    # enlève espaces, CFA, « Prix sur demande », etc.
    digits = re.sub(r"\D", "", str(txt))
    return int(digits) if digits else None

def _float(txt):
    try:
        return float(re.search(r"(\d+(?:\.\d+)?)", txt or "").group(1))
    except (AttributeError, ValueError):
        return None
    


def first_two_words(text):
    words = text.strip().split()
    return " ".join(words[:2]) if words else None

def _first(obj):
    """
    Si obj est une liste non vide on renvoie le 1er élément stripé,
    sinon on renvoie obj tel quel (stripé si string).
    """
    if isinstance(obj, list):
        return str(obj[0]).strip() if obj else None
    return str(obj).strip() if obj else None



class PropertyItem(scrapy.Item):
    id           = scrapy.Field(output_processor=TakeFirst())
    url          = scrapy.Field(output_processor=TakeFirst())
    title        = scrapy.Field(output_processor=TakeFirst())
    price        = scrapy.Field(input_processor=MapCompose(_int),
                                output_processor=TakeFirst())
    bedrooms     = scrapy.Field()
    bathrooms    = scrapy.Field()
    city         = scrapy.Field(output_processor=TakeFirst())
    district     = scrapy.Field(output_processor=TakeFirst())
    description  = scrapy.Field(output_processor=TakeFirst())
    source       = scrapy.Field(output_processor=TakeFirst())
    latitude     = scrapy.Field(output_processor=TakeFirst())
    longitude    = scrapy.Field(output_processor=TakeFirst())
    scraped_at   = scrapy.Field(output_processor=TakeFirst())
    title = scrapy.Field(
        input_processor=MapCompose(str.strip, first_two_words),
        output_processor=TakeFirst()
    )
    statut_annonceur = scrapy.Field()
    nb_annonces = scrapy.Field()
    posted_time = scrapy.Field()
    adresse = scrapy.Field()
    property_type = scrapy.Field()
    statut = scrapy.Field()
    description = scrapy.Field()
    surface_area = scrapy.Field()


class ExpatDakarPropertyItem(scrapy.Item):
    id           = scrapy.Field(output_processor=TakeFirst())
    url          = scrapy.Field(output_processor=TakeFirst())
    title         = scrapy.Field()
    price         = scrapy.Field(input_processor=MapCompose(_int),
                                output_processor=TakeFirst())
    surface_area  = scrapy.Field()
    bedrooms      = scrapy.Field(input_processor=MapCompose(_int),
                                output_processor=TakeFirst())
    bathrooms     = scrapy.Field(input_processor=MapCompose(_int),
                                output_processor=TakeFirst())
    city          = scrapy.Field(output_processor=TakeFirst())
    region        = scrapy.Field(output_processor=TakeFirst())
    description   = scrapy.Field(output_processor=TakeFirst())
    source        = scrapy.Field(output_processor=TakeFirst())
    scraped_at    = scrapy.Field(output_processor=TakeFirst())
    statut        = scrapy.Field(output_processor=TakeFirst())
    posted_time   = scrapy.Field(output_processor=TakeFirst())
    adresse       = scrapy.Field(output_processor=TakeFirst())
    property_type = scrapy.Field(output_processor=TakeFirst())
    member_since  = scrapy.Field(output_processor=TakeFirst())
    listing_id    = scrapy.Field(output_processor=TakeFirst())
    nb_annonces   = scrapy.Field(output_processor=TakeFirst())


class LogerDakarPropertyItem(scrapy.Item):
    id            = scrapy.Field(output_processor=TakeFirst())
    url           = scrapy.Field(output_processor=TakeFirst())
    title         = scrapy.Field(output_processor=TakeFirst())
    price         = scrapy.Field(input_processor=MapCompose(_int),
                                output_processor=TakeFirst())
    surface_area  = scrapy.Field(output_processor=TakeFirst())
    bedrooms      = scrapy.Field(output_processor=TakeFirst())
    bathrooms     = scrapy.Field(output_processor=TakeFirst())
    city          = scrapy.Field(output_processor=TakeFirst())
    region        = scrapy.Field(output_processor=TakeFirst())
    description   = scrapy.Field(output_processor=TakeFirst())
    source        = scrapy.Field(output_processor=TakeFirst())
    scraped_at    = scrapy.Field(output_processor=TakeFirst())
    statut        = scrapy.Field(output_processor=TakeFirst())
    posted_time   = scrapy.Field(output_processor=TakeFirst())
    adresse       = scrapy.Field(output_processor=TakeFirst())
    property_type = scrapy.Field(output_processor=TakeFirst())
    listing_id    = scrapy.Field(output_processor=TakeFirst())