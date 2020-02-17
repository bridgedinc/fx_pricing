from itertools import product
import json
from decimal import Decimal
from urllib.parse import urlencode

import scrapy

from scrapyproject.items import TransferItem
from scrapyproject.utils import get_transfer_pairs

AMOUNTS = [10, 50, 100, 300, 750, 1500, 5000, 25000]


class AzimoSpider(scrapy.Spider):
    name = "azimo"
    custom_settings = {
        'COOKIES_ENABLED': True,
    }

    def start_requests(self):
        for source_country, destination_country in get_transfer_pairs(self.name):
            yield scrapy.Request(
                "https://api.azimo.com/service-tracking/v1/public/track",
                callback=self.parse_tracking,
                headers={"Content-Type": "application/json"},
                meta={"dont_cache": True},
                dont_filter=True,
                cb_kwargs={
                    "scountry": source_country["code3"],
                    "dcountry": destination_country["code3"],
                }
            )

    def parse_tracking(self, response, scountry, dcountry):
        tracking_id = json.loads(response.body)["trackingId"]
        url = (
            "https://azimo.com/en/rest/sendingCountryConfigs/"
            f"{scountry}?payoutCountryIso3Code={dcountry}"
        )
        yield scrapy.Request(
            url,
            callback=self.parse_payment_methods,
            headers={
                "X-Azimo-UTDM": tracking_id,
                "X-Api-Version": "3.15.0",
                "X-App-Version": "LEGO-CLIENT,v4.9.0",
            },
            cb_kwargs={
                "scountry": scountry,
                "dcountry": dcountry,
                "tracking_id": tracking_id,
            }
        )

    def get_method_speed(self, details):
        for detail in details:
            if detail["type"] == "ESTIMATED_DELIVERY_TIME":
                return detail["text"]
        return ""

    def get_payment_methods(self, raw_data):
        items = json.loads(raw_data)["sendingCountryConfigs"]["items"]
        for item in items:
            source_currency = item["currencyIso3Code"]
            for config in item["payoutCountryConfigs"]:
                for currency in config["currencies"]:
                    destination_currency = currency["iso3Code"]
                    for method in currency["deliveryMethods"]:
                        method_type = method["type"]
                        if method_type == "MOBILE_TOP_UP":
                            continue
                        speed = self.get_method_speed(method["options"]["details"])
                        yield method_type, speed, source_currency, destination_currency

    def parse_payment_methods(self, response, scountry, dcountry, tracking_id):
        methods = self.get_payment_methods(response.body)
        for method_type, speed, scurrency, dcurrency in methods:
            params = {
                "sendingCountry": scountry,
                "sendingCurrency": scurrency,
                "receivingCountry": dcountry,
                "receivingCurrency": dcurrency,
                "deliveryMethod": method_type,
            }
            url = "https://api.azimo.com/service-rates/v1/public/prices/current?"
            url += urlencode(params)
            yield scrapy.Request(
                url,
                callback=self.parse_exrate,
                headers={
                    'X-Application-Calculator': 'individual',
                    "X-Azimo-UTDM": tracking_id,
                    "X-Api-Version": "3.15.0",
                    "X-App-Version": "LEGO-CLIENT,v4.9.0",
                },
                cb_kwargs={"speed": speed},
            )

    def parse_exrate(self, response, speed):
        data = json.loads(response.body)
        exrate = Decimal(data["rates"][0]["rate"])
        variants = product(AMOUNTS, ("Debit & Credit Card", "Bank Transfer"))
        for amount, funds_in in variants:
            item = TransferItem()
            item["send_country"] = data["corridor"]["sendingCountry"]
            item["receive_country"] = data["corridor"]["receivingCountry"]
            item["send_currency"] = data["corridor"]["sendingCurrency"]
            item["receive_currency"] = data["corridor"]["receivingCurrency"]
            item["send_amount"] = amount
            item["receive_amount"] = amount * exrate
            item["send_fees"] = data["rates"][0]["adjustments"]["fee"]["min"]["was"]
            item["exrate_service"] = exrate
            item["funds_in"] = funds_in
            item["funds_out"] = data["corridor"]["deliveryMethod"]
            item["speed"] = speed
            yield item
