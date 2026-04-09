## 1. Fix Configuration

- [x] 1.1 [database] Fix `alembic.ini` — replace `%(DATABASE_URL)s` with dummy placeholder
- [x] 1.2 [core-api] Add `./database:/app/database` volume mount to core-api in `docker-compose.yml`

## 2. Verification

- [x] 2.1 [database] Run `docker compose exec core-api sh -c "cd /app/database && alembic upgrade head"` — succeeds
