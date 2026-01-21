ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as base

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm

ARG APT_PACKAGES
ARG PREBUILD_COMMANDS="DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y gcc default-libmysqlclient-dev pkg-config"
ARG POSTBUILD_COMMANDS="pip install -r requirements.txt"
ARG ROOT_DIRECTORY=ANIMALSRESQ
ENV DEPLOY_CMD="gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app"

WORKDIR /app
COPY ${ROOT_DIRECTORY} /app/

RUN if [ -n "$PREBUILD_COMMANDS" ]; then \
      echo "Running prebuild commands"; \
      bash -c "$PREBUILD_COMMANDS"; \
    fi && \
    if [ -n "$POSTBUILD_COMMANDS" ]; then \
      echo "Running postbuild commands"; \
      bash -c "$POSTBUILD_COMMANDS"; \
    fi

CMD ["/bin/sh", "-c", "$DEPLOY_CMD"]


