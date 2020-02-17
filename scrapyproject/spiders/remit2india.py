import json
import re
from decimal import Decimal
from itertools import product
from pprint import pprint
from w3lib.html import remove_tags
from unicodedata import normalize

import scrapy

from scrapyproject.items import TransferItem

AMOUNTS = [10, 50, 100, 300, 750, 1500, 5000, 25000]


class Remit2IndiaSpider(scrapy.Spider):
    """"""

    name = "remit2india"
    custom_settings = {
        "COOKIES_ENABLED": True,
    }
    job = None
    scraper = None

    def extract_exrate(self, response):
        """"""
        for rateid in ("dispSlabWiseGrtRate", "dispSlabWiseIndRate"):
            query = f"span#{rateid}::text"
            value = response.css(query).get()
            if value:
                return Decimal(value)

    def extract_fees(self, response):
        """"""
        fees = []
        query = '//div[@class="transfer_fees_sec"]//tr[1]/td'
        for i, fee in enumerate(response.xpath(query), 1):
            corridor = remove_tags(str(fee.get()))
            corridor = re.findall(r"[\d,+]+", corridor)
            if not corridor:
                continue
            if corridor[1] == "+":
                corridor[1] = "500,000"
            min_value = Decimal(corridor[0].replace(",", ""))
            max_value = Decimal(corridor[1].replace(",", ""))
            is_fee_percent = False
            fee = fee.xpath(f'./../following-sibling::tr/td[{i}]/text()').get()
            fee = re.search("[\d.,%]+", fee)
            if not fee:
                fee = 0
            else:
                fee = fee[0]
                if fee.endswith("%"):
                    is_fee_percent = True
                    fee = Decimal(fee[:-1])
            fees.append((min_value, max_value, fee, is_fee_percent))
        print(fees)
        return fees

    def extract_sending_options(self, response):
        """"""
        sending_options = []
        query = f'//h2[text()="Delivery Time"]/following-sibling::div[1]//tr/td[1]'
        for method in response.xpath(query):
            method_name = method.css("::text").get().strip()
            speed = method.xpath("./following-sibling::td[1]/text()").get()
            sending_options.append((method_name, speed))
        return sending_options

    def get_fee_by_amount(self, amount, fees):
        """"""
        for min_value, max_value, fee, is_fee_percent in fees:
            if min_value <= amount <= max_value:
                if is_fee_percent:
                    fee = amount / Decimal(100.0) * fee
                return fee

    def start_requests(self):
        countries = (
            ("United States", "USA", "USD"),
            ("Canada", "CAN", "CAD"),
            ("Australia", "AUS", "AUD"),
            ("Ireland", "IRE", "EUR"),
            ("United Kingdom", "GBR", "GBP"),
        )
        for country, country_code, currency in countries:
            url = (
                "https://www.remit2india.com/sendmoneytoindia/"
                f"{country.replace(' ', '')}/exchangeRate.jsp"
            )
            method_name = "parse_" + country.replace(" ", "_").lower()
            yield scrapy.Request(
                url,
                callback=self.parse,
                cb_kwargs={
                    "send_country": country_code,
                    "send_currency": currency,
                },
            )

    def parse(self, response, send_country, send_currency):
        fees = self.extract_fees(response)
        exrate = self.extract_exrate(response)
        send_options = self.extract_sending_options(response)
        receive_options = response.css(".receving_opts_sec h3.h3title::text").getall()
        variants = product(AMOUNTS, send_options, receive_options)
        for amount, (funds_in, speed), funds_out in variants:
            fee = self.get_fee_by_amount(amount, fees)
            if fee is None:
                continue
            item = TransferItem()
            item["send_country"] = send_country
            item["receive_country"] = "IND"
            item["send_currency"] = send_currency
            item["receive_currency"] = "INR"
            item["send_amount"] = amount
            item["send_fees"] = fee
            item["receive_amount"] = amount * exrate
            item["exrate_service"] = exrate
            item["funds_in"] = funds_in
            item["funds_out"] = funds_out
            item["speed"] = normalize("NFKD", speed)
            yield item
