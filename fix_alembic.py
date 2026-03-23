import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def reset_alembic():
    # Connect to the database
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        # Drop the memory table
        await conn.execute(text("DROP TABLE IF EXISTS public.alembic_version;"))
    print("✅ Alembic memory successfully wiped! You are ready to migrate.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_alembic())