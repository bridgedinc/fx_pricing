import csv
import json
from itertools import product
from pathlib import Path
from urllib.parse import urlencode

import scrapy

from scrapyproject.items import TransferItem


class InstaremSpider(scrapy.Spider):
    """"""

    name = "instarem"
    custom_settings = {
        'COOKIES_ENABLED': True,
    }
    transfer_amounts = [500, 1000]

    def get_pairs(self):
        """"""
        pairs_file = self.settings["DATA_DIR"] / "transferpairs" / "instarem.csv"
        with pairs_file.open() as fp:
            reader = csv.DictReader(fp)
            for pair in reader:
                yield pair

    def start_requests(self):
        variants = product(self.transfer_amounts, self.get_pairs())
        for amount, pair in variants:
            item = {
                "send_country": pair["send_country"],
                "receive_country": pair["receive_country"],
                "send_currency": pair["send_currency"],
                "receive_currency": pair["receive_currency"],
                "send_amount": amount,
            }
            query = {
                "source_currency": item["send_currency"],
                "source_amount": amount,
                "destination_currency": item["receive_currency"],
            }
            url = "https://www.instarem.com/api/v1/public/payment-method/fee?"
            url += urlencode(query)
            yield scrapy.Request(
                url=url,
                callback=self.parse_funds_in,
                headers={"X-Requested-With": "XMLHttpRequest"},
                dont_filter=True,
                cb_kwargs={"source_item": item},
            )

    def parse_funds_in(self, response, source_item):
        methods = json.loads(response.body)["data"]
        for method in methods:
            query = {
                "source_currency": source_item["send_currency"],
                "destination_currency": source_item["receive_currency"],
                "instarem_bank_account_id": method["key"],
                "source_amount": source_item["send_amount"],
            }
            url = "https://www.instarem.com/api/v1/public/transaction/computed-value?"
            url += urlencode(query)
            item = source_item.copy()
            item["funds_in"] = method["text"]
            yield scrapy.Request(
                url=url,
                callback=self.parse_rate,
                headers={"X-Requested-With": "XMLHttpRequest"},
                cb_kwargs={"item": item},
            )

    def parse_rate(self, response, item):
        item = TransferItem(item)
        data = json.loads(response.body)["data"]
        item["receive_amount"] = data["destination_amount"]
        item["send_fees"] = data["transaction_fee_amount"]
        item["exrate_service"] = data["fx_rate"]
        item["funds_out"] = "Bank Deposit"
        item["speed"] = "1-2 business days"
        yield item
