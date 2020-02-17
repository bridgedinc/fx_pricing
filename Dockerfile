FROM python:3.7-alpine3.9

ENV DJANGO_SETTINGS_MODULE=bridged.settings

WORKDIR /bridged

RUN apk add --update \
        build-base ca-certificates gcc linux-headers \
        libressl-dev libffi-dev libxml2-dev libxslt-dev python3-dev zlib-dev \
        postgresql-dev && \
    rm -rf /var/cache/apk/*

ADD requirements.txt .

RUN pip install -r requirements.txt

ADD . .

RUN mkdir -p logs results

RUN chmod 755 entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
