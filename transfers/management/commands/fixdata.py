from django.core.management.base import BaseCommand

from transfers.models import ScrapeJob, Scraper


class Command(BaseCommand):

    def handle(self, *args, **options):
        scraper = Scraper.objects.filter(name='transferwise')[0]
        jobs = ScrapeJob.objects.filter(processed=False).order_by('id')
        for job in jobs:
            for item in job.items.filter(scraper_id=scraper.id).iterator():
                # total_pay
                if item.total_pay is not None:
                    continue
                if item.send_amount is None or item.send_fees is None:
                    continue
                item.total_pay = item.send_amount
                item.send_amount -= item.send_fees
                if item.exrate_market:
                    item.calculate(item.exrate_market)
                item.save()

            job.processed = True
            job.save()
            print(f"Processing of job={job.id} has finished")
