FROM python:3.12-alpine3.24

# Install dependencies
RUN apk update && apk upgrade --scripts=no apk-tools
RUN apk add python3 python3-dev build-base musl-dev gcc g++ tzdata cargo rust libffi-dev musl-dev
RUN apk add --no-cache freetype-dev \
    fribidi-dev \
    harfbuzz-dev \
    libgcc \
    cargo \
    jpeg-dev \
    lcms2-dev \
    openjpeg-dev \
    rustup \
    tcl-dev \
    tiff-dev \
    tk-dev \
    zlib-dev \
    bash \
    pngquant

# Set timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apk add netcat-openbsd git

# Install supercronic
ARG TARGETARCH
ARG SUPERCRONIC_VERSION=v0.2.33

RUN apk add --no-cache --virtual .fetch-deps curl ca-certificates && \
    case "${TARGETARCH}" in \
        amd64) SUPERCRONIC_ARCH="amd64" ;; \
        arm64) SUPERCRONIC_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    SUPERCRONIC_URL="https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${SUPERCRONIC_ARCH}" && \
    curl -fsSL "$SUPERCRONIC_URL" -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic && \
    apk del .fetch-deps

RUN addgroup -g 5000 ocw \
    && adduser -D -u 5000 -G ocw ocw

USER ocw

ENV PATH="/home/ocw/.local/bin:${PATH}"

RUN pip3 install --upgrade pip
RUN pip3 install django-postgresql psycopg2-binary

COPY --chown=ocw:ocw . /app
WORKDIR /app

COPY --chown=ocw ./crontab /etc/crontab

RUN pip3 install -r requirements.txt

EXPOSE 80
EXPOSE 55230

# establish temporary bare config for making translations
RUN cp /app/carwings/settings.example.py /app/carwings/settings.py
RUN REDIS_HOST="" python manage.py compilemessages
RUN rm -rf /app/carwings

CMD ["bash", "/app/docker/start.sh"]


