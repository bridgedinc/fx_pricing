import json
import logging
from collections import OrderedDict
from decimal import Decimal
from itertools import product
from urllib.parse import urlencode

import scrapy

from scrapyproject.items import TransferItem
from scrapyproject.utils import get_transfer_pairs


def check_for_errors(option, logger, meta):
    """"""
    if option.get('error'):
        if option['error']['code'] == 1220:
            message = 'Limit exceeded: "{0}" > "{1}", {2}'.format(
                meta['send_country']['name'],
                meta['receive_country']['name'],
                meta['send_amount'],
            )
        else:
            message = 'Unknown error: {0} {1}'.format(
                option['error']['code'],
                option['error']['message'],
            )
        logger(message, level=logging.WARNING)
        return option['error']


def get_states(country_code, country_list):
    """"""
    for country in country_list:
        if country['code'] == country_code:
            if country.get('receiverInfoStateRequired'):
                return country['states']
            break

    return [{"code": -1}]


class MoneyGramSpider(scrapy.Spider):
    name = 'moneygram'
    custom_settings = {
        # 'PROXY': 'socks5://proxy:8080',
        # "DOWNLOADER_MIDDLEWARES": {
        #     'scrapyproject.middlewares.ProxyMiddleware': 1,
        # },
        'DOWNLOAD_DELAY': .15,
    }

    transfer_amounts = (100, 200)

    def start_requests(self):
        yield scrapy.Request(
            url='https://consumerapi.moneygram.com/services/capi/api/v1/config/countries',
            headers={'clientKey': 'Basic V0VCXzM4ODQwNTUxLWQ5ZTMtNGJlZS1iZjUyLTNkNDA1ODYwN2UzMjplZjUyNTdkNi1kMDk4LTRmMzktYjFmMS00NTg1OTlkYzQ2MTc='},
        )

    def parse(self, response):
        countries = json.loads(response.body)['countryList']

        for (send_country, receive_country), amount in product(get_transfer_pairs(self.name), self.transfer_amounts):
            send_currency = send_country['currency_code']

            for state in get_states(receive_country['code3'], countries):
                params = OrderedDict(
                    senderCountry=send_country['code3'],
                    senderCurrency=send_currency,
                    receiveCountry=receive_country['code3'],
                    sendAmount=amount,
                )
                if state['code'] != -1:
                    params['receiveState'] = state['code']

                url = 'https://consumerapi.moneygram.com/services/capi/api/v1/sendMoney/feeLookup?' + urlencode(params)
                yield scrapy.Request(
                    url,
                    callback=self.parse_transfers,
                    headers={
                        'clientKey': 'Basic V0VCXzM4ODQwNTUxLWQ5ZTMtNGJlZS1iZjUyLTNkNDA1ODYwN2UzMjplZjUyNTdkNi1kMDk4LTRmMzktYjFmMS00NTg1OTlkYzQ2MTc=',
                    },
                    meta={
                        'send_country': send_country,
                        'send_currency': send_currency,
                        'send_amount': amount,
                        'receive_country': receive_country,
                        'receive_state': state['code'],
                    }
                )
                # TODO Scrape all states
                break

    def parse_transfers(self, response):
        data = json.loads(response.body)

        # if response.meta['receive_country']['code3'] == 'NLD' and \
        #    response.meta['send_country']['code2'] == 'US':
        #     pprint(data)

        for send_option in data['paymentOptions']:
            error = check_for_errors(send_option, self.log, response.meta)
            if error:
                # item['error_message'] = error['message']
                # yield item
                return

            for receive_group in send_option['receiveGroups']:
                for data in receive_group['receiveOptions']:
                    # Пропускаем вариант по просьбе заказчика
                    if send_option['localizedName'] == 'Cash at Location':
                        continue

                    # National currencies only
                    national_currency = response.meta['receive_country']['currency_code']
                    if national_currency != data['receiveCurrency']:
                        continue

                    item = TransferItem()
                    item['send_country'] = response.meta['send_country']['code3']
                    item['receive_country'] = response.meta['receive_country']['code3']
                    item['send_currency'] = response.meta['send_currency']
                    item['send_amount'] = Decimal(response.meta['send_amount'])
                    item['send_fees'] = Decimal(data['sendFees'])
                    # item['send_limit'] = data.get('sendLimit', '')
                    # item['send_taxes'] = data['sendTaxes']
                    # item['receive_state'] = ''
                    # if response.meta['receive_state'] != -1:
                    #     item['receive_state'] = response.meta['receive_state']
                    item['receive_currency'] = data['receiveCurrency']
                    # item['receive_fees'] = data['receiveFees']
                    # item['receive_limit'] = data.get('receiveLimit', '')
                    # item['receive_taxes'] = data['receiveTaxes']
                    item['receive_amount'] = Decimal(data['receiveAmount'])
                    item['exrate_service'] = Decimal(data['exchangeRate'])
                    item['funds_in'] = send_option['localizedName']
                    item['funds_out'] = receive_group['receiveGroupLabel']
                    if item['funds_in'] == 'Online Bank Account':
                        item['speed'] = 'Within 4 days'
                    else:
                        item["speed"] = "The money is typically available for pickup in minutes."
                    yield item
