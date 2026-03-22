import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import random

DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"
engine = create_async_engine(DATABASE_URL, echo=False)


async def seed_history():
    print("📈 Injecting 10 Years of Historical Training Data for St. Christopher (ID: 17)...")

    async with engine.connect() as conn:
        inserts = []
        base_baptisms = 40

        # Generate data from 2015 to 2025 with a slight upward trend and some randomness
        for year in range(2015, 2026):
            base_baptisms += random.randint(-5, 12)  # Simulating realistic parish growth/dips
            inserts.append(f"({17}, {year}, {base_baptisms})")

        sql = f"""
            INSERT INTO public.demographic_trends (parish_id, year, baptism_count)
            VALUES {",".join(inserts)};
        """

        await conn.execute(text(sql))
        await conn.commit()
        print("✅ Historical dataset successfully loaded into the Gold Layer!")


if __name__ == "__main__":
    asyncio.run(seed_history())