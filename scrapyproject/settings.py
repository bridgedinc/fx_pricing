from pathlib import Path
import sys

import django

# Init of djangoitem
sys.path.append(Path(__file__).parent.parent.parent)
django.setup()

BOT_NAME = "scrapyproject"

# See https://doc.scrapy.org/en/latest/topics/autothrottle.html
# AUTOTHROTTLE_ENABLED = True
# AUTOTHROTTLE_START_DELAY = 5
# AUTOTHROTTLE_MAX_DELAY = 60
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# AUTOTHROTTLE_DEBUG = True

COOKIES_DEBUG = False
COOKIES_ENABLED = False

CONCURRENT_REQUESTS = 6
# CONCURRENT_REQUESTS_PER_DOMAIN = 16
# CONCURRENT_REQUESTS_PER_IP = 16

DATA_DIR = Path(__file__).parent / "data"

DEBUG = False

# DEFAULT_REQUEST_HEADERS = {
#   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language': 'en',
# }

DEPTH_PRIORITY = -1

DOWNLOAD_DELAY = 0

DUPEFILTER_DEBUG = True

EXTENSIONS = {
}

HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [401, 403, 500, 503]
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"
HTTPCACHE_GZIP = False

ITEM_PIPELINES = {
   'scrapyproject.pipelines.TransferItemPipeline': 300,
}

NEWSPIDER_MODULE = "scrapyproject.spiders"

PROXY = "http://bridgedint:Bridged_2019@us-wa.proxymesh.com:31280"

REACTOR_THREADPOOL_MAXSIZE = 10

ROBOTSTXT_OBEY = False

# SPIDER_MIDDLEWARES = {
#    'scrapyproject.middlewares.ProjectSpiderMiddleware': 543,
# }

SPIDER_MODULES = ["scrapyproject.spiders"]

TELNETCONSOLE_ENABLED = False
TELNETCONSOLE_PORT = [6023]
TELNETCONSOLE_USERNAME = "scrapy"
TELNETCONSOLE_PASSWORD = "scrapy"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/12.0.3 Safari/605.1.15"
)