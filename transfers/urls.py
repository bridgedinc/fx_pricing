from django.urls import path

from . import views

urlpatterns = [
    path("", views.homepage, name="homepage", kwargs={"set": "today"}),
    path("archive/", views.homepage, name="archive", kwargs={"set": "archive"}),
    path("scrape/", views.run_scraping, name="run_scraping"),
    path("download/<int:pk>/", views.download_csv, name="download_csv"),
]
