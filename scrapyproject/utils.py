import csv
import json
import os
from pathlib import Path


def get_transfer_pairs(service):
    """"""
    pairs_file = Path(__file__).parent / "data" / "transferpairs" / (service + '.json')
    with open(pairs_file) as fp:
        pairs = json.load(fp)
        for pair in map(lambda c: (get_country(c[0]), get_country(c[1])), pairs):
            if not all(pair):
                continue
            yield pair


def get_country(code, field="code2"):
    """"""
    code = code.upper()
    countries_file = f"/bridged/scrapyproject/data/countries.csv"
    countries_file = Path(__file__).parent / "data" / "countries.csv"
    with countries_file.open() as fp:
        reader = csv.DictReader(fp)
        for country in reader:
            if country[field] == code:
                return country


def is_country_exist(code: str, field: str = "code2") -> bool:
    country = get_country(code, field)
    return True if country and country["currency_code"] else False
