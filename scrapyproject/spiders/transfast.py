from datetime import datetime, date
import json
from itertools import product
from urllib.parse import urlencode
from collections import namedtuple

import scrapy

from ..items import TransferItemLoader

Product = namedtuple('Product', ['id', 'speed', 'rate'])

ReceiveCurrency = namedtuple('ReceiveCurrency', ['id', 'code'])

Fee = namedtuple(
    'Fee',
    ['product_id', 'rcurrency_id', 'fee',
     'amount_lower', 'amount_upper',
     'funds_in', 'funds_out']
)


class TransfastSpider(scrapy.Spider):
    name = "transfast"
    custom_settings = {
        "COOKIES_ENABLED": True,
    }

    transfer_amounts = [10, 50]

    _request_token = ''

    def start_requests(self):
        yield scrapy.Request('https://secure.transfast.com/transaction', self.parse_token)

    def parse_token(self, response):
        query = 'input[name=__RequestVerificationToken]::attr(value)'
        self._request_token = response.css(query).get()
        yield scrapy.Request(
            'https://www.transfast.com/api/sitecore/Marketing/GetTransactionCalcInitialDataParams/?senderCountryId=USA',
            callback=self.parse_countries,
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )

    def parse_countries(self, response):
        data = json.loads(response.body)
        countries = data['PerSenderCountryData']['RecipientCountries']
        for country in countries:
            url = 'https://secure.transfast.com/Step1/GetPerRecipientCountryDataJson'
            send_country = data['CoreData']['SelectedSenderCountryId']
            receive_country = country["Id"]
            params = {
                "senderCountryId": send_country,
                "recipientCountryId": receive_country,
                "senderCurrencyId": data["PerSenderCountryData"]["SenderCurrencyId"],
                'isNewCustomerClientSide': 'false',
            }
            yield scrapy.FormRequest(
                url + '?' + urlencode(params),
                callback=self.parse_recipient_country_data,
                formdata={'__requestVerificationToken': self._request_token},
                cb_kwargs={
                    'scountry': send_country,
                    'rcountry': receive_country,
                }
            )

    def parse_recipient_country_data(self, response, scountry, rcountry):
        data = json.loads(response.body)
        products = get_products(data)
        receive_currencies = get_receive_currencies(data['RecipientCurrencies'])
        fees = get_fees(data)
        variants = product(products, receive_currencies, fees, self.transfer_amounts)
        for product_, rcurrency, fee, amount in variants:
            exceeding = exceeding_limit(
                amount, fee.funds_in, fee.funds_out, data['SendingLimits']
            )
            if exceeding: continue
            if fee.product_id != product_.id or \
               fee.rcurrency_id != rcurrency.id or \
               not (fee.amount_lower <= amount <= fee.amount_upper) or \
               (rcurrency.code != 'USD' and not product_.rate):
                continue
            l = TransferItemLoader()
            l.add_value('send_country', scountry)
            l.add_value('receive_country', rcountry)
            l.add_value('send_currency', 'USD')
            l.add_value('receive_currency', rcurrency.code)
            l.add_value('send_fees', fee.fee)
            rate = product_.rate if product_.rate else 1
            l.add_value('exrate_service', rate)
            l.add_value('send_amount', amount)
            l.add_value('receive_amount', amount * rate)
            l.add_value(
                'funds_in', expand_funds_in(fee.funds_in, data['SenderPaymentModes'])
            )
            l.add_value(
                'funds_out',
                expand_funds_out(fee.funds_out, data['RecipientPaymentModes'])
            )
            l.add_value('speed', product_.speed)
            yield l.load_item()


def get_products(data):
    products = []
    for product in data['Products']:
        products.append(get_product(product['ProductId'], data))
    if not products:
        products.append(get_product(None, data))
    return products


def get_product(product_id, data):
    additional_info = data['ProductsAdditionalInfo']
    speed = get_product_speed(product_id, additional_info)
    rate = get_product_rate(product_id, data['Rates'])
    product_ = Product(id=product_id, speed=speed, rate=rate)
    return product_


def get_product_speed(product_id, product_data):
    for product in product_data:
        if product['ProductId'] != product_id:
            continue
        delivery_date = product['EstimatedDeliveryDateTimeSenderTz'].rsplit('.')[0]
        delivery_date = datetime.strptime(delivery_date, '%Y-%m-%dT%H:%M:%S')
        num_days = (delivery_date - datetime.now()).days + 1
        speed = 'Within {0} day'.format(num_days)
        if num_days > 1: speed += 's'
        return speed


def get_product_rate(product_id, rates):
    for rate in rates:
        if rate['ProductId'] == product_id and not rate['IsNewCustomer']:
            return rate['Rate']
    return 0.0


def get_receive_currencies(currencies_raw):
    currencies = []
    for currency in currencies_raw:
        currencies.append(ReceiveCurrency(
            id=currency['RecipientCurrencyTypeId'],
            code=currency['CurrencyCode'],
        ))
    return currencies


def get_fees(data):
    fees = []
    for fee in data['Fees']:
        fees.append(Fee(
            product_id=fee['ProductId'],
            rcurrency_id=fee['RecipientCurrencyType'],
            fee=fee['FeeAmount'],
            amount_lower=fee['AmountRangeLower'],
            amount_upper=fee['AmountRangeUpper'],
            funds_in=fee['SenderPaymentModeId'],
            funds_out=fee['RecipientPaymentModeId'],
        ))
    return fees


def expand_funds_in(mode_id, modes):
    for mode in modes:
        if mode['SenderPaymentModeId'] == mode_id:
            return mode['Name']


def expand_funds_out(mode_id, modes):
    for mode in modes:
        if mode['RecipientPaymentModeId'] == mode_id:
            return mode['Name']


def exceeding_limit(amount, send_mode_id, receive_mode_id, limits) -> bool:
    for limit in limits:
        if send_mode_id == limit['PaywithMethodId'] and \
           receive_mode_id == limit['RecipientPaymentModeId'] and \
           (amount < limit['MinDaily'] or amount > limit['MaxYearly']):
            return True
    return False
