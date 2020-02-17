from django.contrib import admin

from .models import ScrapeJob, Scraper, TransferAmount


class ScraperAdmin(admin.ModelAdmin):
    """"""
    list_display = ('name', "is_active", "details")

admin.site.register(Scraper, ScraperAdmin)


class ScrapeJobAdmin(admin.ModelAdmin):
    """"""
    list_display = ("started_at", "finished_at", "state")

admin.site.register(ScrapeJob, ScrapeJobAdmin)


class TransferAmountAdmin(admin.ModelAdmin):

    list_display = ("value",)

admin.site.register(TransferAmount, TransferAmountAdmin)
