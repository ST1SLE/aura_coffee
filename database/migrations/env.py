# START_MODULE_CONTRACT
#   PURPOSE: Alembic migration entry point — wires the project's SQLAlchemy
#            metadata (shared.models.Base) into Alembic's online/offline runners
#            and resolves the database URL from env without overriding caller-
#            provided values (so test fixtures can redirect at aura_coffee_test).
#   SCOPE:   Imported by Alembic CLI when running `alembic upgrade/downgrade`.
#            Schema-only — no seed data, no app logic (see database/AGENTS.md).
#   DEPENDS: M-SHARED (shared.models.Base), alembic, sqlalchemy, stdlib (os, logging.config).
#   LINKS:   docs/development-plan.xml M-DATABASE, PDD §5.5 (Migrations),
#            database/AGENTS.md "Test database contract".
#   ROLE:    CONFIG
#   MAP_MODE: NONE
# END_MODULE_CONTRACT

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from shared.models import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: не отключать уже созданные логгеры
    # приложения (иначе после миграции в тестах теряются WARNING).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Если URL уже задан явно (например, в тестах), не перезаписываем его.
_placeholder = "driver://user:pass@localhost/dbname"
if config.get_main_option("sqlalchemy.url", _placeholder) == _placeholder:
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

target_metadata = Base.metadata


# START_CONTRACT: run_migrations_offline
#   PURPOSE: Run Alembic migrations in offline mode — emits SQL without an
#            active DB connection (literal_binds=True). Used by `alembic upgrade
#            --sql` to generate migration scripts for review.
#   INPUTS:  none (reads sqlalchemy.url from Alembic config)
#   OUTPUTS: None
#   SIDE_EFFECTS: emits SQL to Alembic's configured output stream; does NOT
#                 touch any database.
#   LINKS:   PDD §5.5, database/AGENTS.md "Schema-only migrations"
# END_CONTRACT: run_migrations_offline
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# START_CONTRACT: run_migrations_online
#   PURPOSE: Run Alembic migrations in online mode against a live PostgreSQL
#            connection. This is the standard path for `alembic upgrade head`
#            in dev, CI, tests, and the docker-compose db-migrate service.
#   INPUTS:  none (reads engine config from Alembic config_ini_section)
#   OUTPUTS: None
#   SIDE_EFFECTS: opens a connection via NullPool, runs DDL inside a single
#                 transaction, mutates the target database schema. Caller-
#                 provided sqlalchemy.url is preserved (test DB redirect).
#   LINKS:   PDD §5.5, database/AGENTS.md "Test database contract"
# END_CONTRACT: run_migrations_online
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
