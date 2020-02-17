import re
import json
from itertools import product

import scrapy

from scrapyproject.items import TransferItemLoader
from scrapyproject.utils import get_country


class RiaAustraliaSpider(scrapy.Spider):

    name = 'ria_australia'
    custom_settings = {
        "COOKIES_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            'scrapyproject.middlewares.ProxyMiddleware': 1,
        },
    }
    handle_httpstatus_list = []
    transfer_amounts = (100,)

    def start_requests(self):
        yield scrapy.Request(
            "https://www.riamoneytransfer.com.au/price-calculator",
            callback=self.parse_countries,
        )

    def parse_countries(self, response):
        query = "input[name=__RequestVerificationToken]::attr(value)"
        token = response.css(query).get()
        match = re.search(r"unmappedViewModel = ({.*?});", response.body.decode())
        if not match:
            raise ValueError("Can't extract countries")
        countries = json.loads(match[1])["Countries"][1]["Options"]
        variants = product(self.transfer_amounts, countries)
        for amount, country in variants:
            yield scrapy.FormRequest(
                "https://www.riamoneytransfer.com.au/send-money-online/countrychange",
                callback=self.parse_fee_and_exhange_rate,
                headers={"X-Requested-With": "XMLHttpRequest"},
                dont_filter=True,
                formdata={
                    "__RequestVerificationToken": token,
                    "SkipPaymentMethods": "false",
                    "countryTo": country["Value"],
                    "AmountFrom": str(amount),
                }
            )

    def parse_fee_and_exhange_rate(self, response):
        data = json.loads(response.body)
        variants = product(data["DeliveryMethodNames"], data["Services"])
        for delivery_method, payment_method in variants:
            l = TransferItemLoader()
            l.add_value("send_country", payment_method["CountryFrom"])
            l.add_value("receive_country", data["CountryTo"])
            l.add_value("send_currency", payment_method["CurrencyFrom"])
            l.add_value("receive_currency", data["CurrencyTo"])
            l.add_value("exrate_service", data["ExchangeRate"])
            l.add_value("send_amount", data["AmountFrom"])
            l.add_value("receive_amount", data["AmountTo"])
            l.add_value("send_fees", payment_method["Fee"])
            l.add_value("funds_in", payment_method["DisplayPaymentMethod"])
            l.add_value("funds_out", delivery_method["Value"])
            l.add_value("speed", "1-4 days")
            yield l.load_item()
