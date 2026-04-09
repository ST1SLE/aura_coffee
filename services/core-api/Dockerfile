FROM python:3.12-slim

WORKDIR /app

COPY packages/shared /app/packages/shared
RUN pip install --no-cache-dir /app/packages/shared

COPY services/core-api /app/services/core-api
RUN pip install --no-cache-dir /app/services/core-api

EXPOSE 8000

CMD ["uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
