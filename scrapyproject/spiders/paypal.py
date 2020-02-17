import json
import logging
from itertools import product
from urllib.parse import urlencode
from random import shuffle

import scrapy
from scrapy.exceptions import CloseSpider

from ..utils import get_country
from ..items import TransferItemLoader

LOGIN_URL = "https://www.paypal.com/us/signin"


class PayPalSpider(scrapy.Spider):
    name = 'paypal'
    custom_settings = {
        "COOKIES_ENABLED": True,
        "CONCURRENT_REQUESTS": 2,
        "HTTPCACHE_ENABLED": False,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapyproject.middlewares.PaypalDownloaderMiddleware": 500,
        },
    }
    handle_httpstatus_list = [403]

    transfer_amounts = (100, 25000)
    credentials = [
        ("tarunadnani94@hotmail.com", "Tarun@2019"),
        ("vvk1234@gmail.com", "Varsha1bridged#"),
        ("vtu@hotmail.com", "Vtu#1357"),
    ]
    username = None
    password = None

    def start_requests(self):
        shuffle(self.credentials)
        yield scrapy.Request(LOGIN_URL, self.login_email)

    def login_email(self, response):
        if not self.credentials:
            raise CloseSpider("no_credentials")
        self.username, self.password = self.credentials.pop()
        self.log(f'Use {self.username} as username to log in')
        yield scrapy.FormRequest.from_response(
            response,
            callback=self.login_password,
            formdata={"login_email": self.username},
        )

    def login_password(self, response):
        login_password = response.css('input[name=login_password]').get()
        if not login_password:
            print(response.text)
            yield scrapy.Request(LOGIN_URL, self.login_email, dont_filter=True)
            return
        yield scrapy.FormRequest.from_response(
            response,
            formdata={"login_password": self.password},
            callback=self.after_login,
        )

    def after_login(self, response):
        # Can't login
        if "try logging" in response.text or \
           response.status == 403 or \
           'verification-failed' in response.url:
            yield scrapy.Request(LOGIN_URL, self.login_email, dont_filter=True)
            return
        yield scrapy.Request(
            "https://www.paypal.com/myaccount/transfer/griffinMetadata?",
            callback=self.parse_countries,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    def parse_countries(self, response):
        countries_data = json.loads(response.body)["griffinSupportedCountries"]
        send_countries = ["US", "CA", "GB", "AU", "DE"]
        receive_countries = [c["countryCode"] for c in countries_data]
        variants = product(send_countries, receive_countries, self.transfer_amounts)
        for send_country, receive_country, amount in variants:
            if send_country == receive_country:
                continue
            receive_country_dict = get_country(receive_country)
            if not receive_country_dict or \
               not receive_country_dict["currency_code"]:
                self.log(
                    "Unknown country code %s" % receive_country, level=logging.WARN
                )
                continue
            send_currency = get_country(send_country)["currency_code"]
            receive_currency = receive_country_dict["currency_code"]
            query = {
                "amount": amount,
                "fromCurrencyCode": send_currency,
                "toCurrencyCode": receive_currency,
                "fromCountryCode": send_country,
                "toCountryCode": receive_country,
                "isPurchase": "false",
            }
            url = "https://www.paypal.com/myaccount/transfer/fx/rates/sent?"
            url += urlencode(query)
            item = dict()
            item["send_country"] = send_country
            item["receive_country"] = receive_country
            item["send_currency"] = send_currency
            item["receive_currency"] = receive_currency
            item["send_amount"] = amount
            yield scrapy.Request(
                url,
                callback=self.parse_fee_and_exchange_rate,
                headers={"X-Requested-With": "XMLHttpRequest"},
                cb_kwargs={"item": item},
            )

    def parse_fee_and_exchange_rate(self, response, item):
        data = json.loads(response.body)["data"]
        for funds_in, send_fee_dict in data["fees"].items():
            l = TransferItemLoader(from_dict=item)
            l.add_value("send_fees", send_fee_dict["fee"])
            l.add_value("exrate_service", data["rate"])
            l.add_value("receive_amount", data["toAmountRaw"])
            l.add_value("funds_in", funds_in)
            l.add_value("funds_out", "Bank Deposit")
            l.add_value("speed", "Within 1 day")
            yield l.load_item()
