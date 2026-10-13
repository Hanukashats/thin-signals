# syntax=docker/dockerfile:1.7
FROM python:3.14.4-slim-bookworm@sha256:fc74d22ffd0d5ac395a4b7bdda75a4539758862c49ebf3005647084631e63789

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TS_ROOT=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcap2=1:2.66-4+deb12u3+b1 \
        libgnutls30=3.7.9-2+deb12u7 \
        libpcre2-8-0=10.42-1+deb12u2 \
        libssl3=3.0.22-1~deb12u1 \
        openssl=3.0.22-1~deb12u1 \
        perl-base=5.36.0-7+deb12u4 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 thin-signals \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /app \
        --shell /usr/sbin/nologin thin-signals

COPY deploy/docker/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps --requirement /tmp/requirements.lock \
    && python -m pip check \
    && rm /tmp/requirements.lock

COPY --chown=10001:10001 pyproject.toml alembic.ini ./
COPY --chown=10001:10001 ts ./ts
COPY --chown=10001:10001 ui ./ui
COPY --chown=10001:10001 data ./data
COPY --chown=10001:10001 .streamlit ./.streamlit

RUN install -d -m 0700 -o 10001 -g 10001 \
        /var/lib/thin-signals/snapshots \
        /var/cache/thin-signals \
        /var/lib/thin-signals-ui

USER 10001:10001

CMD ["uvicorn", "ts.api:app", "--host", "0.0.0.0", "--port", "8095"]
