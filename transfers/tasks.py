from celery import shared_task
from django.core import management


@shared_task
def run_scraping_task():
    management.call_command("run_scraping")
