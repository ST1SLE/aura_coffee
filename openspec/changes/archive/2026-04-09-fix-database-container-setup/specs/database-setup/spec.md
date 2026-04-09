## MODIFIED Requirements

### Requirement: Alembic initialization
The `alembic.ini` SHALL use a dummy placeholder for `sqlalchemy.url` instead of ConfigParser interpolation. The actual URL is set at runtime by `env.py` from `os.environ["DATABASE_URL"]` (INV-015).

Previously: `sqlalchemy.url = %(DATABASE_URL)s` — ConfigParser interpolation conflicting with logging formatters.
Now: `sqlalchemy.url = driver://user:pass@localhost/dbname` — inert placeholder overridden by env.py.

#### Scenario: Alembic reads config without interpolation errors
- **WHEN** Alembic parses `alembic.ini`
- **THEN** no ConfigParser interpolation error occurs regardless of logging formatter strings
