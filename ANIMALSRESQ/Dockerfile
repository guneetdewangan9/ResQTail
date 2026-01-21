ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as base

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm

ARG APT_PACKAGES="apt-get update && apt-get install -y bash curl git build-essential default-libmysqlclient-dev libssl-dev libffi-dev libjpeg-dev libxslt-dev libxml2-dev zlib1g-dev libevent-dev"
ARG PREBUILD_COMMANDS="apt-get update && apt-get install -y gcc default-libmysqlclient-dev pkg-config && pip install -r requirements.txt"
ARG POSTBUILD_COMMANDS="pip install -r requirements.txt"
ARG ROOT_DIRECTORY=ANIMALSRESQ
ENV DEPLOY_CMD="gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app"

WORKDIR /app

COPY ${ROOT_DIRECTORY} /app/

RUN if [ -n "$PREBUILD_COMMANDS" ]; then \
  echo "Running prebuild commands: $PREBUILD_COMMANDS"; \
  sh -lc "$PREBUILD_COMMANDS"; \
fi

RUN if [ -n "$POSTBUILD_COMMANDS" ]; then \
  echo "Running postbuild commands: $POSTBUILD_COMMANDS"; \
  sh -lc "$POSTBUILD_COMMANDS"; \
fi

CMD ["/bin/sh", "-c", "$DEPLOY_CMD"]

