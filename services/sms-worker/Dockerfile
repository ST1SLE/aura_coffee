FROM python:3.12-slim AS base

WORKDIR /app

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir -e /app/packages/shared

COPY services/sms-worker /app/services/sms-worker
RUN pip install --no-cache-dir -e /app/services/sms-worker

CMD ["celery", "-A", "sms_worker.main:celery_app", "worker", "--loglevel=info"]

FROM base AS dev

RUN pip install --no-cache-dir -e "/app/services/sms-worker[dev]"
