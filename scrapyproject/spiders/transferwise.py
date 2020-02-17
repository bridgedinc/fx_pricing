from datetime import date, datetime
import csv
from pathlib import Path
import json
import re
from collections import defaultdict
from itertools import product
from pprint import pprint

import scrapy
from scrapyproject.items import TransferItem

ALLOWED_PAYMENT_OPTIONS = (
    "INTERNATIONAL_DEBIT",
    "DIRECT_DEBIT",
    "BANK_TRANSFER",
    "CREDIT",
    "DEBIT",
    "POLI",
    "SWIFT",
    "IDEAL",
    "TRUSTLY",
    "SOFORT",
    "BILL_PAYMENT",
)


class AuthError(Exception):
    pass


class InitialDataError(Exception):
    pass


class TranferWiseSpider(scrapy.Spider):
    name = "transferwise"
    custom_settings = {
        "COOKIES_ENABLED": True,
    }

    transfer_amounts = [50, 100]

    currency_countries = defaultdict(set)

    def get_transfer_pairs(self, send_currencies, routes):
        for scountry in send_currencies:
            scurrency = scountry[1]
            for route in routes:
                if route["currencyCode"] != scurrency:
                    continue
                for rcurrency in route["targetCurrencies"]:
                    yield scountry, rcurrency["currencyCode"]

    def start_requests(self):
        countries_file = Path(__file__).parent.parent / "data" / "transferwise-countries.csv"
        with countries_file.open() as fp:
            reader = csv.DictReader(fp)
            for country in reader:
                currency = country["Currency"]
                self.currency_countries[currency].add(country["Code3"])
        yield scrapy.Request(
            "https://transferwise.com/",
            meta={"dont_cache": True},
        )

    def parse(self, response):
        """Extracts transfer pairs and auth key."""
        body = response.body.decode()
        match = re.search(r'__PUBLIC_WEB_CLIENT_TOKEN__="([0-9a-f]+)";', body)
        if not match:
            raise AuthError("Can't extract authorization key")
        auth_key = match[1]
        match = re.search(r'__INITIAL_STATE__=(.*?);', body)
        if not match:
            raise InitialDataError("Can't extract initial data")
        initial_data = json.loads(match[1])
        pairs = self.get_transfer_pairs(
            (("USA", "USD"), ("AUS", "AUD"), ("GBR", "GBP"), ("DEU", "EUR"),("CAN", "CAD")),
            initial_data["routes"]["value"]
        )
        variants = product(self.transfer_amounts, pairs)
        for amount, (scountry, rcurrency) in variants:
            data = {
                "sourceAmount": amount,
                "sourceCurrency": scountry[1],
                "targetCurrency": rcurrency,
                "preferredPayIn": None,
                "guaranteedTargetAmount": False,
            }
            yield scrapy.Request(
                "https://transferwise.com/gateway/v2/quotes/",
                method="POST",
                callback=self.parse_quotes,
                headers={
                    "Content-Type": "application/json",
                    "X-Authorization-key": auth_key,
                },
                body=json.dumps(data),
                cb_kwargs={"send_country": scountry[0]},
            )

    def parse_quotes(self, response, send_country):
        quotes = json.loads(response.body)
        for option in quotes["paymentOptions"]:
            if option["disabled"]:
                continue
            if option["payIn"] not in ALLOWED_PAYMENT_OPTIONS:
                continue
            receive_currency = option["targetCurrency"]
            for receive_country in self.currency_countries[receive_currency]:
                item = TransferItem()
                item["send_country"] = send_country
                item["receive_country"] = receive_country
                item["send_currency"] = option["sourceCurrency"]
                item["receive_currency"] = receive_currency
                item["send_amount"] = option["sourceAmount"]
                item["receive_amount"] = option["targetAmount"]
                item["exrate_service"] = quotes["rate"]
                item["send_fees"] = option["fee"]["total"]
                item["funds_in"] = option["payIn"]
                item["funds_out"] = option["payOut"]
                item["speed"] = option["formattedEstimatedDelivery"]
                if item['speed'].startswith("by"):
                    receive_date = datetime.strptime(
                        option["estimatedDelivery"].split("T")[0], "%Y-%m-%d"
                    )
                    receive_date = receive_date.date()
                    delta = receive_date - date.today()
                    num_days = delta.days + 1
                    item["speed"] = f"Within {num_days} day"
                    if num_days > 1:
                        item["speed"] += "s"
                if item['speed'].startswith("in"):
                    item['speed'] = "Within 1 day"
                yield item
