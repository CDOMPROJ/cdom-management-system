import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ==============================================================================
# 1. PATH CONFIGURATION
# ==============================================================================
# Add the backend directory to the Python path so Alembic can find the 'app' module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ==============================================================================
# 2. IMPORT SETTINGS & MODELS
# ==============================================================================
# Import your FastAPI settings to get the DATABASE_URL dynamically
from app.core.config import settings

# Import the declarative Base from your models so Alembic can read your tables
from app.models.all_models import Base

# ==============================================================================
# 3. ALEMBIC CONFIGURATION
# ==============================================================================
# This is the Alembic Config object, providing access to values within alembic.ini
config = context.config

# Interpret the config file for Python logging (sets up the terminal output)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Dynamically inject the DATABASE_URL from your .env file into Alembic
# This prevents you from having to hardcode your password in alembic.ini
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Link your SQLAlchemy Base metadata to Alembic for 'autogenerate' support
target_metadata = Base.metadata

# ==============================================================================
# 4. MIGRATION RUNNERS (OFFLINE & ONLINE)
# ==============================================================================

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL scripts without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Synchronous helper function to run the actual context migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an Asynchronous Engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Establish an async connection and run the synchronous migration helper
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Trigger the asynchronous migration loop."""
    asyncio.run(run_async_migrations())


# Determine which mode Alembic was called in and run the appropriate function
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()