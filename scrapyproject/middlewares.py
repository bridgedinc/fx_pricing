import json
from urllib.parse import parse_qs, urlparse

import requests
import scrapy
from python_anticaptcha import (
    AnticaptchaClient, ImageToTextTask, NoCaptchaTaskProxylessTask
)
from scrapy import signals
from scrapy.exceptions import IgnoreRequest


class ProjectSpiderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, dict or Item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Response, dict
        # or Item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class ProjectDownloaderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ProxyMiddleware(object):

    def process_request(self, request, spider):
        proxy = spider.settings.get('PROXY')
        if proxy:
            request.meta['proxy'] = proxy


class PaypalDownloaderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    max_captcha_attempts = 3

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = AnticaptchaClient(
            "94c9d06a8920ff1cd08bcd00f077524f",
            use_ssl=False,
        )

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        body = response.body.decode()
        if 'name="recaptcha"' in body:
            meta = getattr(request, "meta", {})
            attempt = meta.get("captcha_attempt", 1)
            if attempt > self.max_captcha_attempts:
                raise IgnoreRequest("Number of attempts exceeded")
            captcha_url = response.css("iframe::attr(src)").get()
            u = urlparse(captcha_url)
            query = parse_qs(u.query)
            task = NoCaptchaTaskProxylessTask(captcha_url, query["siteKey"][0])
            job = self.client.createTask(task)
            job.join()
            return scrapy.FormRequest.from_response(
                response,
                callback=request.callback,
                meta={"captcha_attempt": attempt + 1},
                formdata={
                    "recaptcha": job.get_solution_response(),
                },
            )
        elif 'data-captcha-type="silentcaptcha"' in body:
            meta = getattr(request, "meta", {})
            attempt = meta.get("captcha_attempt", 1)
            if attempt > self.max_captcha_attempts:
                raise IgnoreRequest("Number of attempts exceeded")
            session = requests.Session()
            captcha_image_url = response.css(".captcha-image img::attr(src)").get()
            task = ImageToTextTask(session.get(captcha_image_url, stream=True).raw)
            job = self.client.createTask(task)
            job.join()
            return scrapy.FormRequest.from_response(
                response,
                callback=request.callback,
                meta={"captcha_attempt": attempt + 1},
                formdata={
                    "captcha": job.get_captcha_text(),
                },
            )
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class WesternunionMiddleware(object):

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request: scrapy.Request, spider):
        if 'wuconnect' not in request.url and \
           'retailpresentationservice' not in request.url:
            return None
        if request.meta.get('processed'):
            return None
        request.meta['processed'] = True
        if not spider._headers:
            spider.update_request_params()
        for header, value in spider._headers.items():
            request.headers[header] = value
        data = json.loads(request.body)
        if 'wuconnect' in request.url:
            data['security']['session']['id'] = spider._service_session
        if 'retailpresentationservice' in request.url:
            data['security']['session']['id'] = spider._retail_session
        data['security']['client_ip'] = spider._client_ip
        request._set_body(json.dumps(data))

    def process_response(self, request, response, spider):
        if 'wuconnect' not in response.url and \
           'retailpresentationservice' not in response.url:
            return response
        if not response.body or \
          'session has timed out' in response.text or \
          'technical problem' in response.text:
            attempt = request.meta.get('attempt', 1)
            if attempt % 6 == 0:
                request.meta['processed'] = False
                spider._headers = {}
            if attempt == 24:
                raise ValueError('The number of attempts has been exhausted')
            request.meta['attempt'] = attempt + 1
            return request
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)
