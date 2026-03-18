# ---------------------------------
# 1) Build stage: create egg file
# ---------------------------------
FROM python:3.10 AS build-stage

RUN pip install --no-cache-dir scrapyd-client

WORKDIR /build

COPY . .

RUN scrapyd-deploy --build-egg=scrapping_immobli.egg


# ---------------------------------
# 2) Final image: run Scrapyd
# ---------------------------------
FROM python:3.10-alpine

# Build dependencies
RUN apk --no-cache add \
    gcc musl-dev libffi-dev openssl-dev libxml2-dev libxslt-dev \
    && pip install --no-cache-dir scrapyd \
    && apk del gcc musl-dev libffi-dev openssl-dev libxml2-dev libxslt-dev

RUN mkdir -p /src/eggs/scrapping_immobli

# Copy egg from build-stage
COPY --from=build-stage /build/scrapping_immobli.egg /src/eggs/scrapping_immobli/1.egg

# Copy scrapyd.conf
COPY scrapyd.conf /etc/scrapyd/scrapyd.conf

VOLUME /var/lib/scrapyd
VOLUME /etc/scrapyd

EXPOSE 6800

ENTRYPOINT ["scrapyd", "--pidfile="]
