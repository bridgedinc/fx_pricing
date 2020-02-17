import json
import re
from itertools import product
from time import time

import scrapy
from scrapy.http import HtmlResponse

from ..items import TransferItemLoader
from ..utils import is_country_exist

API_TYPES = [
    [
        'retail',
        'https://www.westernunion.com/retailpresentationservice/rest/api/v1.0/FeeInquiryEstimated',
    ],
    [
        'service',
        'https://www.westernunion.com/wuconnect/rest/api/v1.0/FeeInquiryEstimated'
    ]
]

FUNDS_OUT_CODES = {
    'AG': "Cash Pick-Up",
    'BA': "Bank Deposit",
}


class WesternunionSpider(scrapy.Spider):
    name = "westernunion"
    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': .1,
        "DOWNLOADER_MIDDLEWARES": {
            'scrapyproject.middlewares.WesternunionMiddleware': 560,
        },
    }
    handle_httpstatus_list = [406]

    transfer_amounts = [50, 100]

    def start_requests(self):
        yield scrapy.Request(
            'https://www.westernunion.com/us/en/send-money/app/start',
            self.parse_countries_script,
        )

    def parse_countries_script(self, response: HtmlResponse):
        countries_script = response.xpath(
            '//script[contains(@src, "smo-configs")]/@src'
        ).get()
        yield response.follow(countries_script, self.parse_countries)

    def parse_countries(self, response: HtmlResponse):
        matches = re.search(
            r'countryCurrencyDefaults=(.*),fifoDefaults', response.text
        )
        try:
            countries_json = re.sub(r"(\w+):", r'"\1":', matches[1])
        except (TypeError, IndexError):
            raise ValueError("Can't extract receive country")
        receive_countries = []
        for country in json.loads(countries_json)['countries']:
            country = country['country']
            if not country['name'] or \
               country['active'] != 'Y' or \
               not is_country_exist(country['isoCode']):
                continue
            for currency in country['currencies']:
                receive_countries.append((country['isoCode'], currency['currency']))
        variants = product(receive_countries, self.transfer_amounts, API_TYPES)
        for receive_country, amount, (api_type, api_url) in variants:
            data_file = 'westernunion-{0}-data.json'.format(api_type)
            data_file = self.settings['DATA_DIR'] / data_file
            data = json.load(data_file.open())
            country, currency = receive_country
            data["payment_details"]["destination"]["country_iso_code"] = country
            data["payment_details"]["destination"]["currency_iso_code"] = currency
            data["payment_details"]["origination"]["principal_amount"] = str(amount)
            yield scrapy.Request(
                api_url + timestamp(),
                callback=self.parse_transfer_options,
                method='POST',
                body=json.dumps(data),
                meta={'api_type': api_type},
                dont_filter=True,
            )

    def parse_transfer_options(self, response: HtmlResponse):
        if 'error' in response.text:
            self.log(f'Response error: {response.text}')
            return

        for option in self.get_payment_options(response.body):
            details = option['paymentDetails']
            l = TransferItemLoader()
            l.add_value('send_country', details['origination']['countryIsoCode'])
            l.add_value('receive_country', details['destination']['countryIsoCode'])
            l.add_value('send_currency', details['origination']['currencyIsoCode'])
            l.add_value('receive_currency', details['destination']['currencyIsoCode'])
            send_amount = numeric(details['origination']['principalAmount'])
            l.add_value('send_amount', send_amount)
            receive_amount = numeric(details['destination'].get(
                'expectedPayoutAmount', send_amount
            ))
            l.add_value('receive_amount', receive_amount)
            l.add_value(
                'send_fees', numeric(details['fees'].get('charges', 0))
            )
            l.add_value(
                'total_pay',
                numeric(
                    details['origination'].get(
                        'grossAmount', details['origination']['principalAmount']
                    )
                )
            )
            l.add_value('exrate_service', details.get('exchangeRate', 1))
            l.add_value('funds_in', details['paymentType'])
            l.add_value('funds_out', option['funds_out'])
            try:
                max_delivery_days = int(option['wuProduct']['maxDeliveryDays'])
            except KeyError:
                max_delivery_days = 0
            if max_delivery_days < 2:
                speed = 'Within 1 day'
            else:
                speed = f'Within {max_delivery_days} days'
            l.add_value('speed', speed)
            yield l.load_item()

    # Helpers
    def get_payment_options(self, json_data):
        variants = (
            json.loads(json_data)['serviceOptions']['serviceOption'].values()
        )
        for variant in variants:
            for funds_out_code, options in variant.items():
                for option in options:
                    option['funds_out'] = FUNDS_OUT_CODES.get(
                        funds_out_code, funds_out_code
                    )
                    yield option


def timestamp() -> str:
    return '?timestamp=' + str(int(time() * 1000))


def numeric(string: str) -> float:
    return float(string) / 100
