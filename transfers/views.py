from time import sleep

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import ScrapeJob, Scraper
from .tasks import run_scraping_task


@login_required
def homepage(request, set):
    jobs = (
        ScrapeJob.objects
            .filter(state__in=[ScrapeJob.STATE_IN_PROGRESS, ScrapeJob.STATE_FINISHED])
            .order_by("-started_at")
    )
    today = timezone.now().date()
    if set == "archive":
        jobs = jobs.filter(started_at__lt=today)
    else:
        jobs = jobs.filter(started_at__gte=today)

    scrapers = Scraper.objects.all().order_by("-created_at").values("id", "name")

    return render(request, "homepage.html", {
        "jobs": jobs,
        "set": set,
        "scrapers": scrapers,
    })


@login_required
def run_scraping(request):
    run_scraping_task.delay()
    sleep(1)
    return redirect("homepage")


@login_required
def download_csv(request, pk):
    job = get_object_or_404(
        ScrapeJob.objects.filter(state=ScrapeJob.STATE_FINISHED),
        pk=pk
    )
    filename = f"transfers{job.started_at:%m%d%H%M}"
    try:
        scraper = int(request.GET.get("scraper"))
        scraper = Scraper.objects.get(pk=scraper)
        filename += "_" + scraper.spider_name
    except (IndexError, TypeError, ValueError, Scraper.DoesNotExist):
        scraper = None
    finally:
        filename += ".csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="{filename}"'
    )
    result_file = settings.BRIDGED_RESULTS_DIR / filename
    if result_file.is_file():
        with result_file.open() as fp:
            for line in fp:
                response.write(line)
    else:
        job.write_result_rows(fp=response, scraper=scraper)

    return response
