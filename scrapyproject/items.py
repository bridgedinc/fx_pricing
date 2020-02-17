import re

from scrapy.loader import ItemLoader
from scrapy.loader.processors import Identity, Join, MapCompose, TakeFirst
from scrapy_djangoitem import DjangoItem

from .utils import get_country
from transfers.models import ExchangeRate, TransferItem as ScrapedItem


def process_number(value):
    """"""
    number = str(value)
    number = number.strip()
    number = re.sub(r"[^\d.]", "", number)
    return number


def process_country(country):
    """"""
    if len(country) == 2:
        country_dict = get_country(country)
        if country_dict:
            country = country_dict["code3"]
    return country


class ExchangeRateItem(DjangoItem):

    django_model = ExchangeRate


class TransferItem(DjangoItem):

    django_model = ScrapedItem


class TransferItemLoader(ItemLoader):

    default_item_class = TransferItem
    default_output_processor = TakeFirst()

    send_country_in = MapCompose(process_country)
    receive_country_in = MapCompose(process_country)
    send_fees_in = MapCompose(process_number)
    exrate_service_in = MapCompose(process_number)
    receive_amount_in = MapCompose(process_number)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from_dict = kwargs.pop("from_dict", {})
        for field_name, value in from_dict.items():
            self.add_value(field_name, value)
