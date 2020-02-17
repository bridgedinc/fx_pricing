import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

import scrapy
from inline_requests import inline_requests
from scrapy.exceptions import CloseSpider

from scrapyproject.items import ExchangeRateItem


class ExratesSpider(scrapy.Spider):
    name = '_exrates'
    custom_settings = {
        'COOKIES_ENABLED': True,
        'ITEM_PIPELINES': {
            'scrapyproject.pipelines.ExchangeRatePipeline': 300,
        }
    }

    pairs = [("SAR", "INR"), ("NZD", "INR"), ("USD", "EUR"), ("AUD", "KMF")]
    # Identifier for each pair at fxstreet.com
    asset_ids = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._end = datetime.now()
        self._start = self._end - timedelta(days=7)

    def get_history_request(self, asset, headers):
        url = "https://markettools.fxstreet.com/v1/priceProvider/PriceProviderHistory?"
        url += urlencode({
            "request": f"HISTORY {asset} INTRADAY 15 5000 {self._start:%Y%m%d} {self._end:%Y%m%d}",
            "dataLoader": "ttws",
            "timeZone": "UTC"
        })
        return scrapy.Request(
            url=url,
            headers=headers,
            dont_filter=True,
        )

    @staticmethod
    def get_item(pair, date, value):
        item = ExchangeRateItem()
        item["currency_from"] = pair[0]
        item["currency_to"] = pair[1]
        item["datetime"] = date
        item["value"] = value
        return item

    @staticmethod
    def combine_values(values1, values2):
        for value1 in values1:
            for value2 in values2:
                if value1[0] != value2[0]:
                    continue
                yield value1[0], float(value2[1]) / float(value1[1])

    def get_historical_values(self, text, start=None, end=None):
        if start is None and end is None:
            end = self._end
            start = end - timedelta(hours=6)
        extracted_values = self.extract_values(text)
        date = self._start.replace(
            minute=self._start.minute // 15 * 15, second=0, microsecond=0
        )
        while date < self._end:
            value, prev_value = None, None
            for extracted_at, value in extracted_values:
                if extracted_at >= date:
                    if extracted_at > date:
                        value = prev_value
                    break
                prev_value = value
            if value:
                if start <= date <= end:
                    yield date, value
            date += timedelta(seconds=900)

    def extract_values(self, text):
        values = []
        for line in text.split("\n"):
            try:
                time, _, _, _, close_, *_ = line.split(';')
                time = datetime.strptime(time, '%Y-%m-%d-%H-%M')
                values.append((time, close_))
            except ValueError:
                pass
        return values

    # Start
    def start_requests(self):
        if not self.pairs:
            raise CloseSpider("no_pairs")
        self.pairs = map(lambda x: (x[0].upper(), x[1].upper()), self.pairs)
        yield scrapy.Request(
            url="https://www.fxstreet.com/api/AssetApi/GetAssets?cultureName=en",
            callback=self.parse_asset_ids,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    def parse_asset_ids(self, response):
        response.selector.remove_namespaces()
        for asset in response.xpath('//assetresponse'):
            name = asset.xpath("./name/text()").get()
            if '/' not in name:
                continue
            pair = tuple(name.split("/"))
            self.asset_ids[pair] = asset.xpath("./priceprovidercode/text()").get()
        yield scrapy.FormRequest(
            url="https://authorization.fxstreet.com/token",
            callback=self.auth,
            meta={"dont_cache": True},
            formdata={"grant_type": "domain", "client_id": "client_id"},
        )

    @inline_requests
    def auth(self, response):
        token = json.loads(response.body)
        headers = {"Authorization": f"{token['token_type']} {token['access_token']}"}
        for pair in self.pairs:
            asset = self.asset_ids.get(pair)
            if asset:
                found = False
                resp = yield self.get_history_request(asset, headers)
                for value in self.get_historical_values(resp.text):
                    yield self.get_item(pair, *value)
                    if not found: found = True
                if found: continue

            # There are no such pair on the site or no data for it
            # Trying to determine the exchange rate through USD
            # If one of the currencies is already USD, it will not work
            if pair[0] == "USD":
                continue
            values = []
            for currency in pair:
                asset = self.asset_ids.get(("USD", currency))
                if not asset:
                    self.log("No values for %s" % str(pair))
                    break
                resp = yield self.get_history_request(asset, headers)
                values.append(list(self.get_historical_values(resp.text)))
            if len(values) != 2:
                continue
            for value in self.combine_values(values[0], values[1]):
                yield self.get_item(pair, *value)
