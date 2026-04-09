FROM python:3.12-slim

WORKDIR /app

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY services/sms-worker /app/services/sms-worker
RUN pip install --no-cache-dir /app/services/sms-worker

CMD ["celery", "-A", "sms_worker.main:celery_app", "worker", "--loglevel=info"]
