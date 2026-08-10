"""
Alembic environment configuration for database migrations.
Supports async database connections.
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import sys
import os

# Add parent directory to path to import shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.database import Base, metadata
from dotenv import load_dotenv

load_dotenv()

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL from environment
# Convert async URL to sync for Alembic migrations
database_url = os.getenv("DATABASE_URL", "")
if database_url.startswith("postgresql+asyncpg://"):
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

# Remove sslmode parameter for sync driver compatibility
if database_url and "sslmode" in database_url:
    database_url = database_url.split("&sslmode")[0]

config.set_main_option("sqlalchemy.url", database_url)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    This configures the context with just a URL and not an Engine.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    In this scenario we need to create an Engine and associate a connection with the context.
    """
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
