from decimal import Decimal
import json
from itertools import product
import re

import scrapy

from scrapyproject.items import TransferItem


class SendPageError(Exception):
    pass


class RemitlySpider(scrapy.Spider):
    name = "remitly"
    custom_settings = {
        "COOKIES_ENABLED": True,
    }

    transfer_amounts = [500, 1000]

    def start_requests(self):
        for country in ["us", "au", "ca", "de", "gb"]:
            yield scrapy.Request(
                f"https://www.remitly.com/{country}/en",
                dont_filter=True,
                cb_kwargs={"country": country},
            )

    def parse(self, response, country):
        query = '//h5[text()="Send Money To"]/following-sibling::div//a/@href'
        for i, a in enumerate(response.xpath(query).getall()):
            yield response.follow(
                a,
                callback=self.parse_country,
                meta={"cookiejar": country + str(i)},
                dont_filter=True,
            )

    def parse_country(self, response):
        yield scrapy.Request(
            "https://www.remitly.com/users/get_started",
            callback=self.parse_item,
            meta={"cookiejar": response.meta["cookiejar"]},
            dont_filter=True,
        )

    def parse_item(self, response):
        match = re.search(r'window.__bootstrap = ({.*?});', response.body.decode())
        if not match:
            raise SendPageError()
        data = json.loads(match[1])["data"]
        send_options = []
        for p in data["products"]:
            product_type = p["product_type"]
            speed = p.get("default_delivery_promise", "")
            if speed and speed.startswith("20"):
                speed = "Within 5 days"
            for method in p["payment_methods"]:
                for rate in data["forex_rates"]:
                    if rate["product_type"] == product_type and \
                       rate["payment_method"] == method:
                        send_options.append(
                            (product_type, method, speed, rate["cross"], rate["rate"])
                        )
        receive_options = set()
        for destination_type in data["destination_type_config"].keys():
            for d in data["destinations"]:
                if d["destination_type"] == destination_type:
                    receive_options.add((destination_type, d["receive_market"]))

        variants = product(self.transfer_amounts, send_options, receive_options)
        for amount, send_option, receive_option in variants:
            _, funds_in, speed, cross, rate = send_option
            rate = Decimal(rate)
            funds_out, market = receive_option
            receive_currency = cross.split("/")[1]
            if receive_currency != market.split(":")[1]:
                continue
            for price in data["prices"]["payment_method_prices"]:
                amount_lower = Decimal(price["amount_range_lower"].split()[0])
                amount_upper = Decimal(price["amount_range_upper"].split()[0])
                if price["payment_method"] == funds_in and \
                   price["conduit"].endswith(receive_currency) and \
                   amount_lower <= amount <= amount_upper:
                    item = TransferItem()
                    item["send_country"] = data["country_details"][0]["iso3"]
                    item["receive_country"] = data["country_details"][1]["iso3"]
                    item["send_currency"] = data["currency_details"][0]["iso3"]
                    item["receive_currency"] = receive_currency
                    item["send_amount"] = amount
                    item["receive_amount"] = rate * amount
                    item["exrate_service"] = rate
                    item["send_fees"] = Decimal(price["price"].split()[0])
                    if price["percentage_price"]:
                        item["send_fee"] += amount / 100.0 * price["percentage_price"]
                    item["funds_in"] = funds_in
                    item["funds_out"] = funds_out
                    item["speed"] = speed if speed else _
                    yield item
                    break
