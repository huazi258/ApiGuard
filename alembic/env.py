"""Alembic environment using the application SQLite connection factory."""

from logging.config import fileConfig

from alembic import context

from apiguard.config import Settings
from apiguard.infrastructure.persistence.database import (
    create_sqlite_engine,
    sqlite_url_from_path,
)
from apiguard.infrastructure.persistence.orm import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""

    settings = Settings()
    context.configure(
        url=sqlite_url_from_path(settings.database_path),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with the same engine and PRAGMA configuration as runtime."""

    engine = create_sqlite_engine(Settings().database_path)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
