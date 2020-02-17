from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from twisted.internet import defer

from transfers.models import ScrapeJob, Scraper, TransferAmount


class NoActiveScrapersError(Exception):
    pass


class Command(BaseCommand):
    help = "Run scrapers"

    def handle(self, *args, **options):
        job = ScrapeJob()
        job.save()

        try:
            active_scrapers = Scraper.objects.active_scrapers(settings.BRIDGED_SPIDERS_DIR)
            if not active_scrapers:
                raise NoActiveScrapersError

            scrapy_settings = get_project_settings()
            if not settings.DEBUG:
                filename = f"scrapy{timezone.now():%Y%m%d%H%M}.log"
                scrapy_settings["LOG_FILE"] = settings.BRIDGED_SCRAPY_LOGS_DIR / filename
                scrapy_settings["LOG_STDOUT"] = True
            process = CrawlerProcess(scrapy_settings)

            @defer.inlineCallbacks
            def crawl():
                transfer_amounts = TransferAmount.objects.active_amounts()
                for scraper in active_scrapers:
                    yield process.crawl(
                        scraper.spider_name,
                        job=job,
                        scraper=scraper,
                        transfer_amounts=transfer_amounts,
                    )
                yield process.crawl("_exrates", pairs=job.get_unique_pairs(), job=job)
                process.stop()
            crawl()
            process.start()

            exrates = dict()
            for rate in job.exrates.all():
                key = (rate.datetime.isoformat(), rate.currency_from, rate.currency_to)
                exrates[key] = rate.value

            for item in job.items.iterator():
                exrate_market = item.find_market_rate(exrates)
                if not exrate_market:
                    continue
                item.exrate_market, item.exrate_market_datetime = exrate_market
                item.calculate(item.exrate_market)
                item.save()

            filename = f"transfers{job.started_at:%m%d%H%M}.csv"
            result_file = settings.BRIDGED_RESULTS_DIR / filename
            with result_file.open("w") as fp:
                job.write_result_rows(fp)

            job.state = job.STATE_FINISHED

        except NoActiveScrapersError:
            pass
        except Exception as e:
            print(e)
        finally:
            if job.state == job.STATE_IN_PROGRESS:
                job.state = job.STATE_FINISHED_WITH_ERROR
            job.finished_at = timezone.now()
            job.save()
