import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.all_models import Base

# Remember to update your password!
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"


async def build_tenant_tables():
    print("🏗️ Cloning tables into the Cathedral's schema...")

    # We use schema_translate_map to dynamically tell SQLAlchemy to build in the parish schema
    engine = create_async_engine(
        DATABASE_URL,
        execution_options={"schema_translate_map": {None: "parish_mansa_cathedral"}}
    )

    async with engine.begin() as conn:
        # This executes the CREATE TABLE commands for the specific tenant
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Cathedral schema fully populated! Ready for Sacraments.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(build_tenant_tables())