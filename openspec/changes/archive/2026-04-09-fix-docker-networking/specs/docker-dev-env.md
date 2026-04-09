## docker-dev-env

### MODIFIED: Vite proxy target
- **Previously:** `http://localhost:8000`
- **Now:** `http://core-api:8000`
- **File:** `web/customer/vite.config.ts`

### MODIFIED: Nginx service dependencies
- **Previously:** depends on `web-customer`, `web-admin` only
- **Now:** also depends on `core-api`
- **File:** `docker-compose.yml`

### MODIFIED: Postgres healthcheck command
- **Previously:** `pg_isready -U ${POSTGRES_USER:-aura}`
- **Now:** `pg_isready -U ${POSTGRES_USER:-aura} -d ${POSTGRES_DB:-aura_coffee}`
- **File:** `docker-compose.yml`
