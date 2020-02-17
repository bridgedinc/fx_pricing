import csv
from pathlib import Path

from scrapy.exceptions import DropItem


class TransferItemPipeline(object):

    def __init__(self):
        self.mapping_values = []
        standardization_file = (
            Path(__file__).parent / 'data' / 'standardization.csv'
        )
        with standardization_file.open() as f:
            reader = csv.DictReader(f)
            for rec in reader:
                self.mapping_values.append(rec)

    def process_item(self, item, spider):
        if "send_fees" not in item:
            raise DropItem()
        if hasattr(spider, "job"):
            item["job"] = spider.job
        if hasattr(spider, "scraper"):
            item["scraper"] = spider.scraper
        # Standardization
        for field in ("funds_in", "funds_out", "speed"):
            old_value = item.get(field, "")
            item[field] = self.standardizate(spider.name, field, old_value)
        if spider.name == 'instarem':
            if item['send_currency'] in ('AUD', 'USD') \
               and item['funds_in'] != 'Bank Transfer':
                raise DropItem
            if item['send_currency'] == 'CAD' \
               and item['funds_in'] == 'INTERAC e-Transfer':
                item["funds_in"] = 'Bank Transfer'
        if spider.name == 'orbitremit':
            if item["funds_in"] == 'POLi Transfer':
                raise DropItem
        if spider.name == 'remit2india':
            if item["funds_in"] == 'Bank Transfer (Express)':
                raise DropItem
        if spider.name == 'ria':
            if item["send_country"] == 'ESP' and item["funds_in"] == 'DirectBank':
                item["funds_in"] = 'Bank Transfer'
        if spider.name == 'worldremit':
            if item["send_currency"] == 'CAD' \
               and item["funds_in"] == 'INTERAC e-Transfer':
                item["funds_in"] = 'Bank Transfer'
        # total_pay
        item["send_amount"] = float(item["send_amount"])
        item["send_fees"] = float(item["send_fees"])
        if spider.name in ("instarem", 'transferwise'):
            item["total_pay"] = item["send_amount"]
            item["send_amount"] -= item["send_fees"]
        else:
            item["total_pay"] = item["send_amount"] + item["send_fees"]
        item.save()
        return item
        
    def standardizate(self, scraper, field, value):
        for rec in self.mapping_values:
            if rec["scraper"] == scraper and \
               rec["field"] == field and \
               rec["old_value"].lower() == value.lower():
                return rec["new_value"]
        return value


class ExchangeRatePipeline(object):

    def process_item(self, item, spider):
        if hasattr(spider, "job"):
            item["job"] = spider.job
        item.save()
        return item
