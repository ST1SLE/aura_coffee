## Tasks

### 1. Docker Compose fixes

- [x] 1.1 [docker] `docker-compose.yml` — fix postgres healthcheck: add `-d ${POSTGRES_DB:-aura_coffee}` to `pg_isready` command
- [x] 1.2 [docker] `docker-compose.yml` — add `core-api` to nginx `depends_on`

### 2. Vite proxy fix

- [x] 2.1 [web-customer] `web/customer/vite.config.ts` — change proxy target from `http://localhost:8000` to `http://core-api:8000`

### 3. Route protection fix

- [x] 3.1 [web-customer] `web/customer/src/App.tsx` — move `HomePage` route inside `ProtectedRoute` wrapper

### 4. SMS worker task discovery fix

- [x] 4.1 [sms-worker] `services/sms-worker/src/sms_worker/tasks/__init__.py` — import `send_otp_sms` from `otp` module so Celery discovers it
