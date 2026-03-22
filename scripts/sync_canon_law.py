import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# ==============================================================================
# SYSADMIN UTILITY: MULTI-TENANT SCHEMA SYNCHRONIZER
# ==============================================================================
# Run this script to push database structural changes to ALL registered parishes.

DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"
engine = create_async_engine(DATABASE_URL, echo=False)


async def sync_all_tenants():
    print("🚀 Initiating Multi-Tenant Database Synchronization...")

    # Changed from engine.begin() to engine.connect() to resolve IDE type-hinting warnings
    async with engine.connect() as conn:
        # 1. Fetch all active parish schemas from the global public table
        result = await conn.execute(text("SELECT name, schema_name FROM public.parishes"))
        parishes = result.fetchall()

        if not parishes:
            print("⚠️ No parishes found in the global registry.")
            return

        print(f"🌍 Found {len(parishes)} parish(es). Beginning synchronization loop...\n")

        # 2. Loop through every parish and apply the DDL changes
        for parish_name, schema_name in parishes:
            print(f"🔄 Syncing Schema: [{schema_name}] for {parish_name}...")

            try:
                # Switch connection to this specific parish's schema
                await conn.execute(text(f'SET search_path TO "{schema_name}"'))

                # --- APPLY CANON LAW UPDATES ---
                # We use IF NOT EXISTS to ensure the script is safe to run multiple times

                # Update Marriages
                await conn.execute(text("""
                                        ALTER TABLE marriages
                                            ADD COLUMN IF NOT EXISTS groom_religion_category public.religioncategory NOT NULL DEFAULT 'CATHOLIC',
                                            ADD COLUMN IF NOT EXISTS groom_religion_specific VARCHAR,
                                            ADD COLUMN IF NOT EXISTS bride_religion_category public.religioncategory NOT NULL DEFAULT 'CATHOLIC',
                                            ADD COLUMN IF NOT EXISTS bride_religion_specific VARCHAR;
                                        """))

                # Update Confirmations
                await conn.execute(text("""
                                        ALTER TABLE confirmations
                                            ADD COLUMN IF NOT EXISTS dob DATE;
                                        """))

                print(f"✅ Success: [{schema_name}] is fully up to date.")

            except Exception as e:
                # If a schema fails, we log it but continue the loop for the other parishes
                print(f"❌ Error syncing [{schema_name}]: {e}")

        # 3. Explicitly commit all the changes (Required in SQLAlchemy 2.0 when using connect())
        await conn.commit()

    print("\n🏁 Multi-Tenant Synchronization Complete!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(sync_all_tenants())