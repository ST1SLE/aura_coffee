## MODIFIED Requirements

### Requirement: Docker Compose stack
The `docker-compose.yml` core-api service SHALL mount `./database:/app/database` so that Alembic migrations can be executed inside the container.

Previously: core-api only mounted `packages/shared/src` and `services/core-api/src`.
Now: core-api additionally mounts `./database:/app/database`.

#### Scenario: Run migrations inside container
- **WHEN** a developer runs `docker compose exec core-api sh -c "cd /app/database && alembic upgrade head"`
- **THEN** Alembic connects to PostgreSQL and applies all pending migrations
