import csv
import datetime as dt

from django.db import models
from django.utils import timezone


class ScraperManager(models.Manager):

    def active_scrapers(self, spider_dir):
        active_scrapers = []
        for scraper in self.get_queryset().filter(is_active=True).order_by('id'):
            # Service scrapers
            if scraper.spider_name.startswith("_"):
                continue
            scraper_file = spider_dir.joinpath(scraper.spider_name + ".py")
            if not scraper_file.is_file():
                continue
            active_scrapers.append(scraper)
        return active_scrapers


class Scraper(models.Model):

    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    details = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    objects = ScraperManager()

    class Meta:
        db_table = "companies"

    def __str__(self):
        return self.name

    @property
    def spider_name(self):
        return self.name.lower()


class ScrapeJob(models.Model):

    STATE_IN_PROGRESS = 1
    STATE_FINISHED = 100
    STATE_FINISHED_WITH_ERROR = 101
    STATE_CHOICES = (
        (STATE_IN_PROGRESS, "In progress"),
        (STATE_FINISHED, "Successfully finished"),
        (STATE_FINISHED_WITH_ERROR, "Finished with error"),
    )

    state = models.PositiveSmallIntegerField(
        choices=STATE_CHOICES, default=STATE_IN_PROGRESS
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    processed = models.BooleanField(default=False)

    class Meta:
        db_table = "jobs"

    def is_inprogress(self):
        return self.state == self.STATE_IN_PROGRESS

    def is_finished(self):
        return self.state in (self.STATE_FINISHED, self.STATE_FINISHED_WITH_ERROR)

    def duration(self):
        finished_at = self.finished_at or timezone.now()
        time = finished_at - self.started_at
        time -= dt.timedelta(microseconds=time.microseconds)
        return time

    def get_unique_pairs(self):
        """"""
        pairs = (
            self.items
                .distinct("send_currency", "receive_currency")
                # Clean TransferItem ordering
                .order_by("send_currency", "receive_currency")
                .values_list("send_currency", "receive_currency")
        )
        return pairs

    def write_result_rows(self, fp, scraper=None):
        distinct_fields = [f.name for f in TransferItem._meta.fields if f.name not in ('id', 'scraper_id', 'scraped_at', 'created_at')]
        fieldnames = [f.name for f in TransferItem._meta.fields] + ["scraper__details"]
        exclude = ("id", "job", "scraper", "created_at")
        fieldnames = [f for f in fieldnames if f not in exclude]
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        items = self.items.distinct(*distinct_fields).select_related("scraper").values(*fieldnames)
        if scraper:
            items = items.filter(scraper=scraper)
        for item in items.iterator():
            writer.writerow(item)


class ExchangeRate(models.Model):

    currency_from = models.CharField(max_length=3)
    currency_to = models.CharField(max_length=3)
    value = models.DecimalField(max_digits=20, decimal_places=4)
    datetime = models.DateTimeField()
    job = models.ForeignKey(
        ScrapeJob,
        on_delete=models.CASCADE,
        related_name="exrates",
        # For testing without Django
        null=True,
    )

    class Meta:
        db_table = "exchange_rates"


class ScrapedItem(models.Model):

    job = models.ForeignKey(
        ScrapeJob,
        on_delete=models.CASCADE,
        related_name="items",
        # For testing without Django
        null=True,
    )
    scraper = models.ForeignKey(
        Scraper,
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class TransferItem(ScrapedItem):

    STATUS_OK = 1
    STATUS_ERROR = 2
    STATUS_CHOICES = (
        (STATUS_OK, "OK"),
        (STATUS_ERROR, "Error"),
    )

    send_country = models.CharField(max_length=3)
    receive_country = models.CharField(max_length=3)
    send_currency = models.CharField(max_length=3)
    receive_currency = models.CharField(max_length=3)
    send_amount = models.DecimalField(max_digits=20, decimal_places=4)
    receive_amount = models.DecimalField(max_digits=20, decimal_places=4)
    send_fees = models.DecimalField(max_digits=20, decimal_places=4)
    exrate_service = models.DecimalField(max_digits=20, decimal_places=4)
    exrate_market = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    exrate_market_datetime = models.DateTimeField(null=True)
    funds_in = models.CharField(max_length=100)
    funds_out = models.CharField(max_length=250)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=STATUS_OK)
    error_details = models.CharField(max_length=500, null=True, blank=True)
    spread = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    no_loss_trans = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    actual_trans = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    fx_cut = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    fee_conversion = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    total_premium = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    take_rate = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    speed = models.CharField(max_length=300, null=True)
    scraped_at = models.DateTimeField(auto_now_add=True, null=True)
    total_pay = models.DecimalField(max_digits=20, decimal_places=4, null=True)

    class Meta:
        db_table = "transfer_items"
        ordering = ["scraper_id", "send_country", "receive_country", "send_amount"]

    def calculate(self, exmarket_value):
        """"""
        self.spread = abs(exmarket_value - self.exrate_service) / exmarket_value * 100
        self.no_loss_trans = self.send_amount * exmarket_value
        self.actual_trans = self.send_amount * self.exrate_service
        self.fx_cut = self.no_loss_trans - self.actual_trans
        self.fee_conversion = self.send_fees * exmarket_value
        self.total_premium = self.fx_cut + self.fee_conversion
        self.take_rate = self.total_premium / self.no_loss_trans * 100

    def find_market_rate(self, rates):
        """"""
        if self.send_currency == self.receive_currency:
            return 1, None
        rounded_datetime = self.scraped_at.replace(
            minute=self.scraped_at.minute // 15 * 15, second=0, microsecond=0,
        )
        key = (rounded_datetime.isoformat(), self.send_currency, self.receive_currency)
        rate = rates.get(key)
        if rate:
            return rate, rounded_datetime
        # Found the latest rate
        found_rate = None
        for key_, rate in rates.items():
            market_datetime = key_[0]
            if key_[1:] == key[1:]:
                if found_rate is None or \
                   market_datetime > found_rate[1]:
                    found_rate = rate, market_datetime
        return found_rate


class TransferAmountManager(models.Manager):

    def active_amounts(self):
        return (
            self.get_queryset().filter(is_active=True).values_list("value", flat=True)
        )


class TransferAmount(models.Model):

    value = models.PositiveSmallIntegerField(unique=True)
    is_active = models.BooleanField(default=True)

    objects = TransferAmountManager()

    class Meta:
        db_table = "transfer_amounts"
        ordering = ("value",)
