import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridged.settings')

app = Celery('bridged')
app.config_from_object('django.conf:settings')

app.conf.update(
    worker_max_tasks_per_child=1,
    broker_pool_limit=None
)

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'run_scrapers': {
        'task': 'transfers.tasks.run_scraping_task',
        'schedule': crontab(minute="0", hour="0"),
    },
}
