## Affected Modules

- [docker] — `docker-compose.yml`, `vite.config.ts`
- [web-customer] — `App.tsx`

## Design Decisions

### DD-1: Vite proxy target uses Docker service name

Vite dev server runs inside Docker. The proxy target MUST use Docker DNS name `core-api` instead of `localhost`.

No env-variable abstraction — the project runs exclusively via Docker Compose.

### DD-2: Nginx startup ordering via depends_on

Nginx MUST start after `core-api` is available. Adding `depends_on` with `core-api` (without health condition) is sufficient — nginx tolerates brief upstream unavailability after initial DNS resolution succeeds.

### DD-3: Postgres healthcheck targets correct database

`pg_isready` MUST specify `-d aura_coffee` to match `POSTGRES_DB`. Without it, pg_isready defaults to a database named after the user (`aura`), which does not exist.

### DD-4: Root route requires authentication

`HomePage` (`/`) MUST be wrapped in `ProtectedRoute` to match the auth test plan expectation that unauthenticated access to `/` redirects to `/login`.

## Migration Strategy

No database migrations. All changes are configuration and routing.
