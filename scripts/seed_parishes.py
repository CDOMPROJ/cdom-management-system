import sys
import os
import asyncio
import re

# ==============================================================================
# CRITICAL PATH FIX
# ==============================================================================
# This calculates the absolute path to the 'backend' directory and adds it to
# Python's system path so it can successfully find the 'app' module.
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

# Now Python knows exactly where to find these!
from app.models.all_models import DeaneryModel, ParishModel

# ==============================================================================
# DATABASE CONFIGURATION
# ==============================================================================
# Replace 'YourPasswordHere' with your actual PostgreSQL password
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ==============================================================================
# THE CDOM ARCHITECTURE (6 Deaneries, 31 Parishes)
# ==============================================================================
CDOM_STRUCTURE = {
    "Kashikishi": [
        "St. Peter", "St. Paul", "Our Lady of the Rosary",
        "Mary Help of Christians", "St. Don Bosco"
    ],
    "Kawambwa": [
        "St. Mary", "St. Theresa of the Child Jesus", "St. Andrew",
        "St. Joseph the Worker", "Our Lady of Peace"
    ],
    "Kabunda": [
        "St. Stephen", "St. James", "Uganda Martyrs",
        "Kacema Musuma", "Our Lady of Victory"
    ],
    "Mansa": [
        "Mansa Cathedral", "St. Christopher", "St. Michael the Archangel",
        "St. John the Baptist", "St. Francis of Assisi", "St. Augustine",
        "St. Francis de Sales", "St. John Paul II"
    ],
    "Lubwe": [
        "St. Joseph Husband of Mary", "St. Anthony of Padua", "St. Margaret"
    ],
    "Samfya": [
        "St. John Maria Vianney", "Holy Family", "Christ the King",
        "St. Peter the Apostle", "St. Monica", "Sacred Heart of Jesus"
    ]
}


def generate_schema_name(parish_name: str) -> str:
    """
    Converts a standard name into a safe PostgreSQL schema name.
    Example: 'St. John the Baptist' -> 'parish_st_john_the_baptist'
    """
    clean_name = re.sub(r'[^a-zA-Z0-9]+', '_', parish_name.lower()).strip('_')
    return f"parish_{clean_name}"


# ==============================================================================
# SEEDING LOGIC
# ==============================================================================
async def seed_database():
    print("==================================================")
    print("INITIATING CDOM DATABASE SEEDER")
    print("==================================================\n")

    async with AsyncSessionLocal() as session:
        # Ensure we are operating in the public schema
        await session.execute(text('SET search_path TO public'))

        total_deaneries_added = 0
        total_parishes_added = 0

        for deanery_name, parishes in CDOM_STRUCTURE.items():
            # 1. Check if Deanery exists
            query = await session.execute(select(DeaneryModel).where(DeaneryModel.name == deanery_name))
            deanery = query.scalar_one_or_none()

            if not deanery:
                print(f"[+] Creating Deanery: {deanery_name}")
                deanery = DeaneryModel(name=deanery_name)
                session.add(deanery)
                await session.commit()
                await session.refresh(deanery)
                total_deaneries_added += 1
            else:
                print(f"[~] Deanery '{deanery_name}' already exists. Skipping.")

            # 2. Check and Insert Parishes for this Deanery
            for parish_name in parishes:
                schema_name = generate_schema_name(parish_name)

                # CRITICAL FIX: Check if the schema_name exists, NOT the parish_name.
                # This perfectly avoids the unique constraint violation.
                p_query = await session.execute(
                    select(ParishModel).where(ParishModel.schema_name == schema_name)
                )
                parish = p_query.scalar_one_or_none()

                if not parish:
                    print(f"    -> Adding Parish: {parish_name} (Schema: {schema_name})")
                    new_parish = ParishModel(
                        name=parish_name,
                        deanery_id=deanery.id,
                        schema_name=schema_name
                    )
                    session.add(new_parish)
                    total_parishes_added += 1
                else:
                    pass  # Silently skip existing parishes

        try:
            # Final commit for all the accumulated parishes
            await session.commit()
            print("\n==================================================")
            print("SEEDING COMPLETE!")
            print(f"New Deaneries Added: {total_deaneries_added}")
            print(f"New Parishes Added:  {total_parishes_added}")
            print("==================================================")
        except Exception as e:
            await session.rollback()
            print(f"\n[!] Error during final commit: {e}")


if __name__ == "__main__":
    # Run the async function
    asyncio.run(seed_database())