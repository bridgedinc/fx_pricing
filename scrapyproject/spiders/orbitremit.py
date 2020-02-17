import json
from itertools import product
from urllib.parse import urlencode

import scrapy

from scrapyproject.items import TransferItem, TransferItemLoader

SEND_COUNTRIES = (
    ('GBR', 'GBP'),
    ('AUS', 'AUD'),
    ('NZL', 'NZD'),
)

RECEIVE_COUNTRIES = (
    ("AUS", "AUD"),
    ("AUT", "EUR"),
    ("BGD", "BDT"),
    ("BEL", "EUR"),
    ("CYP", "EUR"),
    ("DNK", "DKK"),
    ("EST", "EUR"),
    ("FIN", "EUR"),
    ("FRA", "EUR"),
    ("DEU", "EUR"),
    ("GRC", "EUR"),
    ("IND", "INR"),
    ("IDN", "IDR"),
    ("IRL", "EUR"),
    ("ITA", "EUR"),
    ("LVA", "EUR"),
    ("LTU", "EUR"),
    ("LUX", "EUR"),
    ("MYS", "MYR"),
    ("MLT", "EUR"),
    ("NPL", "NPR"),
    ("NLD", "EUR"),
    ("NZL", "NZD"),
    ("NOR", "EUR"),
    ("PHL", "PHP"),
    ("POL", "PLN"),
    ("PRT", "EUR"),
    ("SGP", "SGD"),
    ("SVK", "EUR"),
    ("SVN", "EUR"),
    ("ZAF", "ZAR"),
    ("ESP", "EUR"),
    ("LKA", "LKR"),
    ("SWE", "SEK"),
    ("THA", "THB"),
    ("GBR", "GBP"),
    ("USA", "USD"),
    ("VNM", "VND"),
)


class OrbitRemitSpider(scrapy.Spider):
    name = "orbitremit"
    custom_settings = {}

    transfer_amounts = [500, 1000]

    def start_requests(self):
        variants = product(SEND_COUNTRIES, RECEIVE_COUNTRIES)
        for send_country, receive_country in variants:
            if send_country == receive_country:
                continue
            send_country_code, send_currency = send_country
            receive_country_code, receive_currency = receive_country
            q = {
                'send_currency': send_currency,
                'payout_currency': receive_currency,
            }
            yield scrapy.Request(
                'https://secure.orbitremit.com/api/v2/rate.json?' + urlencode(q),
                callback=self.parse_exchange_rate,
                headers={
                    'Accept': 'application/json, text/plain, */*"',
                },
                dont_filter=True,
                cb_kwargs={
                    'item_': {
                        'send_country': send_country_code,
                        'send_currency': send_currency,
                        'receive_country': receive_country_code,
                        'receive_currency': receive_currency,
                    }
                }
            )

    def parse_exchange_rate(self, response: scrapy.http.HtmlResponse, item_: dict):
        rate = float(json.loads(response.body)["data"]['rate'])
        for amount in self.transfer_amounts:
            q = {
                "send": item_["send_currency"],
                "payout": item_["receive_currency"],
                "amount": amount,
            }
            item = item_.copy()
            item["exrate_service"] = rate
            item["send_amount"] = amount
            item["receive_amount"] = amount * rate
            yield scrapy.Request(
                "https://www.orbitremit.com/api/fees?" + urlencode(q),
                callback=self.parse_fee,
                dont_filter=True,
                cb_kwargs={
                    "item_": item
                },
            )

    def parse_fee(self, response, item_):
        data = json.loads(response.body)["data"]
        payment_options = ["Bank Transfer"]
        if item_["send_country"] == "AUS":
            payment_options.append('POLi')
        for funds_in in payment_options:
            l = TransferItemLoader(TransferItem(item_))
            l.add_value('send_fees', data['fee'])
            l.add_value('funds_in', funds_in)
            l.add_value('funds_out', data["recipient_type"])
            l.add_value('speed', '24 hours')
            yield l.load_item()
