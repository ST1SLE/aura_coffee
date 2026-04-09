## ADDED Requirements

### Requirement: FastAPI application entry point
`services/core-api/` SHALL contain a FastAPI application instance accessible as `core_api.main:app`. The application SHALL be runnable via `uvicorn core_api.main:app`.

#### Scenario: Start core-api
- **WHEN** uvicorn starts with `core_api.main:app`
- **THEN** the server binds to the configured host/port and accepts HTTP requests

### Requirement: Health check endpoint
The core-api SHALL expose `GET /health` that returns HTTP 200 with a JSON body `{"status": "ok"}`. This endpoint SHALL NOT require authentication.

#### Scenario: Health check returns ok
- **WHEN** a client sends `GET /health`
- **THEN** the response status is 200 and the body is `{"status": "ok"}`

### Requirement: CORS configuration
The core-api SHALL configure CORS middleware. Allowed origins SHALL be read from the `CORS_ORIGINS` environment variable (INV-015) as a comma-separated list. In development, it SHALL default to `["http://localhost:5173"]`.

#### Scenario: CORS allows configured origins
- **WHEN** a preflight request arrives from an origin listed in `CORS_ORIGINS`
- **THEN** the response includes appropriate `Access-Control-Allow-Origin` headers

### Requirement: Settings via pydantic-settings
All configuration SHALL be loaded via a `pydantic-settings` `BaseSettings` class reading from environment variables (INV-015). Required settings: `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`. No secrets SHALL be hardcoded.

#### Scenario: Missing required env var
- **WHEN** the application starts without `DATABASE_URL` set
- **THEN** pydantic-settings raises a validation error before the server accepts requests

### Requirement: SQLAlchemy session factory
The core-api SHALL configure a SQLAlchemy 2.0 `sessionmaker` bound to the engine created from `DATABASE_URL`. A FastAPI dependency SHALL yield a session per request and close it after the response.

#### Scenario: Database session lifecycle
- **WHEN** a request handler declares a dependency on the database session
- **THEN** it receives an active `Session` that is committed on success and rolled back on exception
