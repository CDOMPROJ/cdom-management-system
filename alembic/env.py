import asyncio
import os
import sys
from logging.config import fileConfig
from dotenv import find_dotenv, load_dotenv

# ==================== ROBUST .env LOADING (searches up the directory tree) ====================
load_dotenv(find_dotenv())

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ==================== FORCE CORRECT ALEMBIC IMPORT ====================
from alembic import context  # type: ignore

# ==================== PATH SETUP ====================
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

# Import the declarative Base
from app.models.all_models import Base

# this is the Alembic Config object
config = context.config

# ==================== SET DATABASE_URL FROM .env ====================
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set.\n"
        "1. Create a file named .env in the backend root folder\n"
        "2. Copy the content from .env.example into it\n"
        "3. Fill in your real DATABASE_URL value"
    )

config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target metadata for autogenerate
target_metadata = Base.metadata


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


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()