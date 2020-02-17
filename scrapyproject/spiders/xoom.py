import csv
import json
from pathlib import Path
from urllib.parse import urlencode

import scrapy

from scrapyproject.items import TransferItemLoader
from ..utils import get_country


class XoomSpider(scrapy.Spider):
    """"""

    name = "xoom"
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            'scrapyproject.middlewares.ProxyMiddleware': 1,
        },
    }

    transfer_amounts = (1000,)
    receive_methods = ["Bank Deposit", "Cash Pickup"]

    def extract_fees(self, response):
        """"""
        for funds_out in self.receive_methods:
            query = '//p[contains(text(), $method)]/..'
            fee_container = (
                response.xpath(query, method=funds_out) or
                response.css(".xvx-table--fee__body")
            )
            payment_methods = fee_container.xpath('.//tr/td[1]')
            for method in payment_methods:
                funds_in = method.css("::text").get("").strip(" †")
                fee = method.xpath('./../td[2]/text()').get("").strip()
                yield (funds_in, funds_out, fee)

    @staticmethod
    def get_speed(receive_country, funds_out):
        speed_file = Path(__file__).parent.parent / "data" / "xoom-speed.csv"
        with speed_file.open() as fp:
            reader = csv.DictReader(fp)
            for speed_record in reader:
                if speed_record["Country"] == receive_country:
                    return speed_record.get(funds_out, "")

    def start_requests(self):
        yield scrapy.Request("https://www.xoom.com", callback=self.parse_countries)

    def parse_countries(self, response):
        countries = response.css('#headerCountryPicker option')
        for country in countries:
            if country.attrib["value"] == "choose-country":
                continue
            yield response.follow(country.attrib["value"], callback=self.parse_country)

    def parse_country(self, response):
        item = dict()
        item["send_country"] = response.css("#sourceCountryCode::attr(value)").get()
        query = "#destinationCountryCode::attr(value)"
        item["receive_country"] = response.css(query).get()
        query = "#sourceCurrencyCode option[selected=true]::attr(value)"
        item["send_currency"] = response.css(query).get()
        query = "#destinationCurrencyCode option[selected=true]::attr(value)"
        item["receive_currency"] = response.css(query).get(
            default=response.css("#destinationCurrencyCode::attr(value)").get()
        )
        for amount in self.transfer_amounts:
            item["send_amount"] = amount
            query = {
                "sourceCountryCode": item["send_country"],
                "sourceCurrencyCode": item["send_currency"],
                "destinationCountryCode": item["receive_country"],
                "destinationCurrencyCode": item["receive_currency"],
                "sendAmount": item["send_amount"],
            }
            yield scrapy.Request(
                "https://www.xoom.com/calculate-fee-table?" + urlencode(query),
                callback=self.parse_rate_and_fees,
                headers={"X-Requested-With": "XMLHttpRequest"},
                cb_kwargs={"item": item.copy()},
            )

    def parse_rate_and_fees(self, response, item):
        json_data = response.css("#jsonData::text").get()
        rate_data = json.loads(json_data)["data"]
        for funds_in, funds_out, send_fee in self.extract_fees(response):
            l = TransferItemLoader(from_dict=item)
            l.add_value("exrate_service", rate_data["fxRate"])
            l.add_value("receive_amount", rate_data["receiveAmount"])
            l.add_value("send_fees", send_fee)
            l.add_value("funds_in", funds_in)
            l.add_value("funds_out", funds_out)
            l.add_value("speed", self.get_speed(item["receive_country"], funds_out))
            yield l.load_item()
