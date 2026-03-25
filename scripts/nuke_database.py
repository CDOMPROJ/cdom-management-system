import asyncio
import sys
import os
from sqlalchemy import text

# Ensure the app module can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import engine

async def nuke_db():
    async with engine.begin() as conn:
        print("Initiating Nuclear Reset...")
        # This completely destroys all tables, data, and Alembic tracking history
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        # This rebuilds an empty, fresh schema ready for new tables
        await conn.execute(text("CREATE SCHEMA public;"))
        print("✅ Database is completely clean and reset.")

if __name__ == "__main__":
    asyncio.run(nuke_db())