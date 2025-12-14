FROM python:3.10-alpine

# Install dependencies
RUN apk update && apk add python3 python3-dev build-base musl-dev gcc g++ tzdata cargo rust libffi-dev musl-dev
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
    pngquant \
    dcron

# Set timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apk add netcat-openbsd git
RUN pip3 install --upgrade pip
RUN pip3 install django-mysql django-postgresql gunicorn daphne gevent psycopg2-binary


# Copy code
COPY . /app
WORKDIR /app

RUN pip3 install -r requirements.txt

RUN /usr/bin/crontab /app/crontab

EXPOSE 80
EXPOSE 55230

CMD ["bash", "/app/docker/start.sh"]


