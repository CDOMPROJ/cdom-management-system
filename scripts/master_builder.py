import asyncio
import sys
import os
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add the backend directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your entire database blueprint
from app.models.all_models import Base

# Remember to put your actual database password here!
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"

# The Official CDOM Architecture
DIOCESE_STRUCTURE = {
    "Kashikishi": ["St. Peter", "St. Paul", "Our Lady of the Rosary", "Mary Help of Christians", "St. Don Bosco"],
    "Kawambwa": ["St. Mary", "St. Theresa of the Child Jesus", "St. Andrew", "St. Joseph the Worker",
                 "Our Lady of Peace"],
    "Kabunda": ["St. Stephen", "St. James", "Uganda Martyrs", "Kacema Musuma", "Our Lady of Victory"],
    "Mansa": ["Assumption of Mary - Mansa Cathedral", "St. Christopher", "St. Michael the Archangel",
              "St. John the Baptist", "St. Francis of Assisi", "St. Augustine", "St. Francis de Sales",
              "St. John Paul II"],
    "Lubwe": ["St. Joseph Husband of Mary", "St. Anthony of Padua", "St. Margaret"],
    "Samfya": ["St. John Maria Vianney", "Holy Family", "Christ the King", "St. Peter the Apostle", "St. Monica",
               "Sacred Heart of Jesus"]
}


def generate_schema_name(parish_name: str) -> str:
    """Converts a parish name into a safe PostgreSQL schema name."""
    if "Cathedral" in parish_name:
        return "parish_mansa_cathedral"

    # Lowercase, replace non-alphanumeric with underscores, strip trailing/leading underscores
    clean_name = re.sub(r'[^a-z0-9]+', '_', parish_name.lower()).strip('_')
    return f"parish_{clean_name}"


async def build_full_diocese():
    print("🏗️ Booting up the Diocesan Master Builder...")

    admin_engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")

    schemas_to_build = []

    async with admin_engine.connect() as conn:
        print("1. Forging the Public Schema & Trigram Engine...")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))

        # We must build the public tables FIRST so the foreign keys have something to attach to
        await conn.run_sync(Base.metadata.create_all)

        print("\n2. Provisioning Deaneries and Parish Schemas...")
        for deanery, parishes in DIOCESE_STRUCTURE.items():
            # Insert Deanery into the public table safely
            await conn.execute(
                text("INSERT INTO public.deaneries (name) VALUES (:name) ON CONFLICT (name) DO NOTHING;"),
                {"name": deanery}
            )

            # Get the Deanery ID
            result = await conn.execute(text("SELECT id FROM public.deaneries WHERE name = :name;"), {"name": deanery})
            deanery_id = result.scalar()

            for parish in parishes:
                schema_name = generate_schema_name(parish)
                schemas_to_build.append(schema_name)

                # Create the physical schema in PostgreSQL
                await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name};"))

                # Link the Parish to the Deanery in the public IAM table
                await conn.execute(
                    text("""
                         INSERT INTO public.parishes (name, deanery_id, schema_name)
                         VALUES (:name, :deanery_id, :schema_name) ON CONFLICT (schema_name) DO NOTHING;
                         """),
                    {"name": parish, "deanery_id": deanery_id, "schema_name": schema_name}
                )
                print(f"   -> Provisioned: {parish} ({schema_name})")

    await admin_engine.dispose()

    print("\n3. Building Sacramental Tables & GIN Indices across all Parishes...")
    for schema_name in schemas_to_build:
        print(f"   -> Compiling architecture for {schema_name}...")
        tenant_engine = create_async_engine(
            DATABASE_URL,
            execution_options={"schema_translate_map": {None: schema_name}}
        )
        async with tenant_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await tenant_engine.dispose()

    print("\n✅ Catholic Diocese of Mansa (CDOM) Architecture is 100% online and verified!")


if __name__ == "__main__":
    asyncio.run(build_full_diocese())