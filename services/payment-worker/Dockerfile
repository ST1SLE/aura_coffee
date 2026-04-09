FROM python:3.12-slim

WORKDIR /app

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY services/payment-worker /app/services/payment-worker
RUN pip install --no-cache-dir /app/services/payment-worker

CMD ["celery", "-A", "payment_worker.main:celery_app", "worker", "--loglevel=info"]
