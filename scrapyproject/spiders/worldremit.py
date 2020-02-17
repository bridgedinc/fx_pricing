import json
from itertools import product
from urllib.parse import urlencode

import scrapy

from ..items import TransferItemLoader


class WorldRemitSpider(scrapy.Spider):
    """
    A simple API can be found at # https://www.worldremit.com/en/money-transfer.
    """
    name = 'worldremit'
    custom_settings = {}

    transfer_amounts = (100, 200)
    send_counties = ("us", "gb", "ca", "au", "de")
    services = ('BNK', 'CSH')

    def start_requests(self):
        yield scrapy.Request(
            "https://www.worldremit.com/en/money-transfer", self.parse_receive_countries
        )

    def parse_receive_countries(self, response):
        receive_countries = response.css("#selectTo option::attr(value)").getall()
        receive_countries = list(filter(lambda x: x != "0", receive_countries))
        if "gb" not in receive_countries:
            receive_countries.append("gb")
        countries = product(self.send_counties, receive_countries)
        for send_country, receive_country in countries:
            if send_country == receive_country:
                continue
            yield scrapy.Request(
                f"https://api.worldremit.com/api/country/{send_country}/{receive_country}?state=dc",
                self.parse_services,
                cb_kwargs={
                    "transfer_params": {
                        "send_country": send_country,
                        "receive_country": receive_country,
                    },
                },
            )

    def parse_services(self, response, transfer_params):
        services = json.loads(response.body)["services"]
        services = filter(lambda x: x['code'] in self.services, services)
        for service in services:
            params = transfer_params.copy()
            params["funds_out"] = service["name"]
            yield scrapy.Request(
                f"https://api.worldremit.com/api/country/{params['send_country']}/correspondents/{params['receive_country']}/products/{service['code']}",
                self.parse_correspondents,
                cb_kwargs={
                    "transfer_params": params,
                    "service": service["code"],
                },
            )

    def parse_correspondents(self, response, transfer_params, service):
        correspondents = json.loads(response.body)
        correspondents = filter(
            lambda x: x['product_code'] == 'CSH' or 'Business account' not in x['name'],
            correspondents
        )
        variants = product(correspondents, self.transfer_amounts)
        for correspondent, amount in variants:
            params = transfer_params.copy()
            params["speed"] = correspondent["time_to_pay_out"]
            url = f"https://api.worldremit.com/api/calculate/{params['send_country']}/{service}?"
            url += urlencode({
                "amount": amount,
                "receiveCountry": params["receive_country"],
                "isSendAmount": 'true',
                "correspondentId": correspondent['id'],
            })
            yield scrapy.Request(
                url,
                self.parse_details,
                cb_kwargs={"transfer_params": params},
            )

    def parse_details(self, response, transfer_params):
        data = json.loads(response.body)
        for method in data["PaymentMethods"]:
            l = TransferItemLoader(from_dict=transfer_params)
            l.add_value('send_currency', data['SendCurrency'])
            l.add_value('receive_currency', data['ReceiveCurrency'])
            l.add_value('send_amount', data['Send'])
            l.add_value('receive_amount', data['Receive'])
            l.add_value('send_fees', data['Fees'])
            l.add_value('exrate_service', data['ExchangeRate'])
            l.add_value('funds_in', method['name'])
            yield l.load_item()
