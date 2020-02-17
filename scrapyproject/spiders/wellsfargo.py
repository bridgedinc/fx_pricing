import json
import re
from itertools import product

import scrapy

from scrapyproject.items import TransferItem

from ..utils import get_country


class WellsFargoSpider(scrapy.Spider):

    name = "wellsfargo"
    custom_settings = {}
    transfer_amounts = (500, 1000)
    payment_options = (
        ("Wells Fargo Bank Account", "2-3 business days"),
        ("Non Wells Fargo Bank Account", "3-4 business days"),
    )

    def start_requests(self):
        yield scrapy.Request(
            "https://www.wellsfargo.com/international-remittances/cost-estimator/",
            callback=self.parse_countries,
        )

    def parse_countries(self, response):
        countries = response.css("#country option")
        for country in countries:
            if country.attrib["value"] == "selectOne":
                continue
            receive_country = country.attrib["value"]
            yield scrapy.FormRequest(
                "https://www.wellsfargo.com/as/grs/country",
                callback=self.parse_receiving_locations,
                method="POST",
                headers={"X-Requested-With": "XMLHttpRequest"},
                formdata={"country": receive_country, "lang": "en"},
            )

    def parse_receiving_locations(self, response):
        locations = json.loads(response.body)["rnmMap"]
        for location, _ in locations.items():
            request = response.request.copy()
            request = request.replace(
                url="https://www.wellsfargo.com/as/grs/country/rnm",
                callback=self.parse_receiving_methods,
                body=request.body.decode() + f"&location={location}",
            )
            yield request

    def parse_receiving_methods(self, response: scrapy.http.HtmlResponse):
        methods = json.loads(response.body)["paymentTypes"]
        variants = product(self.transfer_amounts, methods)
        for amount, method in variants:
            request = response.request.copy()
            request = request.replace(
                url="https://www.wellsfargo.com/as/grs/country/rnm/paymentMethod/amount",
                callback=self.parse_fee_and_rate,
                body=request.body.decode() + f"&method={method}&sendAmount={amount}",
            )
            yield request

    def parse_fee_and_rate(self, response):
        data = json.loads(response.body)
        if data["responseCode"] != "success":
            return
        for funds_in, speed in self.payment_options:
            item = TransferItem()
            item["send_country"] = "USA"
            item["receive_country"] = get_country(data["receivingCountryCode"])["code3"]
            item["send_currency"] = "USD"
            item["send_fees"] = re.sub(r"[^\d.]", "", data["formattedTransferFeeString"])
            item["send_amount"] = data["requestedRawAmount"]
            item["receive_amount"], item["receive_currency"] = (
                data["formattedDeliveyAmount"].split()
            )
            item["receive_amount"] = item["receive_amount"].replace(",", "")
            item["exrate_service"] = 1
            if data["fxRateMapFlag"]:
                # "1 USD = 10,352.2103 DOP" — 10352.2103
                item["exrate_service"] = data["formattedFxRate"].split()[-2].replace(",", "")
            item["funds_in"] = funds_in
            item["funds_out"] = data["paymentMethod"]
            item["speed"] = speed
            yield item
