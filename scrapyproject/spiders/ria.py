import json
from itertools import product

import scrapy

from scrapyproject.items import TransferItemLoader
from scrapyproject.utils import get_country


class RiaSpider(scrapy.Spider):

    name = 'ria'
    custom_settings = {
        "COOKIES_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            'scrapyproject.middlewares.ProxyMiddleware': 1,
        },
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 522, 524, 408, 400],
    }
    transfer_amounts = (100,)

    def get_auth_request(self, country, callback, cb_kwargs=None):
        """"""
        country = country.upper()
        culture = country.lower()
        if country in ("US", "GB", "CA", "AU"):
            culture = "en"
        current_page = f"https://www.riamoneytransfer.com/{country.lower()}/{culture}"
        return scrapy.Request(
            "https://public.riamoneytransfer.com/Authorization/session",
            callback=callback,
            headers={
                "Referer": current_page,
                "CultureCode": culture + "-" + country,
                "IsoCode": country,
                "Current-Page": current_page,
            },
            meta={"dont_cache": True},
            dont_filter=True,
            cb_kwargs=cb_kwargs,
        )

    def get_auth_header(self, text):
        """"""
        token = json.loads(text)["authToken"]
        return f"{token['tokenType'].capitalize()} {token['jwtToken']}"

    def start_requests(self):
        for code in ("us", "gb", "ca", "es"):
            yield self.get_auth_request(code, self.auth_countries)

    def auth_countries(self, response: scrapy.http.HtmlResponse):
        request = response.request.copy()
        request = request.replace(
            url="https://public.riamoneytransfer.com/MoneyTransferCalculator/Initialize",
            callback=self.parse_countries,
            cb_kwargs=None,
        )
        request.headers["Authorization"] = self.get_auth_header(response.body)
        yield request

    def parse_countries(self, response):
        send_country = response.request.headers["IsoCode"].decode().split(": ")[-1]
        form = json.loads(response.body)["formData"]["MoneyTransferCalculatorForm"]
        fields = form["formFields"]
        options = None
        for field in fields:
            if field["id"] == "Countries":
                options = field["options"]
                break
        if options is None:
            raise ValueError(f"Can't extract receive countries for {send_country}")
        receive_countries = [o["value"] for o in options if o["value"]]
        for country in receive_countries:
            yield self.get_auth_request(
                send_country, self.auth_country, {"receive_country": country}
            )

    def auth_country(self, response: scrapy.http.HtmlResponse, receive_country):
        send_country = response.request.headers["IsoCode"].decode().split(": ")[-1]
        request = response.request.copy()
        payload = {
            "Selections": {
                "amountFrom": "",
                "countryTo": receive_country,
                "currencyTo": None,
                "deliveryMethod": None,
                "paymentMethod": None,
                "currencyFrom": get_country(send_country)["currency_code"],
            }
        }
        request = request.replace(
            url="https://public.riamoneytransfer.com/MoneyTransferCalculator/Calculate",
            callback=self.parse_methods,
            method="POST",
            body=json.dumps(payload),
            cb_kwargs=None,
        )
        request.headers["Authorization"] = self.get_auth_header(response.body)
        request.headers["Content-Type"] = "application/json;charset=utf-8"
        yield request

    def parse_methods(self, response: scrapy.http.HtmlResponse):
        data = json.loads(response.body)
        options = data["model"]["transferDetails"]["transferOptions"]
        currencies = []
        for currency in options["currencies"]:
            if currency["isDefaultCurrency"]:
                currencies.append(currency["currencyCode"])
                break
        delivery_methods = [m["value"] for m in options["deliveryMethods"]]
        payment_methods = [m["value"] for m in options["paymentMethods"]]
        variants = product(
            self.transfer_amounts, currencies, delivery_methods, payment_methods
        )
        limits = data["model"]["transferDetails"]["calculations"]["sendAmountLimit"]
        send_min = limits["minimumSendFromAmount"]
        send_max = limits["maximumSendFromAmount"]
        for amount, receive_currency, delivery_method, payment_method in variants:
            if not (send_min <= amount <= send_max):
                continue
            request = response.request.copy()
            payload = json.loads(request.body)["Selections"]
            payload.update(
                amountFrom=amount,
                currencyTo=receive_currency,
                deliveryMethod=delivery_method,
                paymentMethod=payment_method,
            )
            request = request.replace(
                callback=self.parse_fee_and_exchange_rate,
                body=json.dumps({"Selections": payload}),
            )
            yield request

    def parse_fee_and_exchange_rate(self, response):
        details = json.loads(response.body)["model"]["transferDetails"]
        l = TransferItemLoader()
        send_country = response.request.headers["IsoCode"].decode().split(": ")[-1]
        l.add_value("send_country", send_country)
        receive_country = details["selections"]["countryTo"]
        l.add_value("receive_country", receive_country)
        l.add_value("send_currency", details["selections"]["currencyFrom"])
        l.add_value("receive_currency", details["selections"]["currencyTo"])
        l.add_value("exrate_service", details["calculations"]["exchangeRate"])
        l.add_value("send_amount", details["selections"]["amountFrom"])
        l.add_value("receive_amount", details["calculations"]["amountTo"])
        l.add_value("send_fees", details["calculations"]["transferFee"])
        l.add_value("funds_in", details["selections"]["paymentMethod"])
        l.add_value("funds_out", details["selections"]["deliveryMethod"])
        l.add_value("speed", "1-4 days")
        yield l.load_item()
