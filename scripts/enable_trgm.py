import asyncio
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add the backend directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Remember to update your password to match your setup!
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"


async def enable_trigram_engine():
    print("⚙️ Waking up the PostgreSQL Trigram Search Engine...")
    engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        # This tells PostgreSQL to load the fuzzy search module
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))

    print("✅ Trigram Engine Online! Ready for high-speed indexing.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(enable_trigram_engine())