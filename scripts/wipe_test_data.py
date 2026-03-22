import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# ==============================================================================
# SYSADMIN UTILITY: CLEAN SLATE PROTOCOL
# ==============================================================================
# WARNING: This script wipes all transactional data (Sacraments, Audits, Logs)
# across the entire diocese while preserving users and parish infrastructure.

DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"
engine = create_async_engine(DATABASE_URL, echo=False)

# The tables inside each parish schema that need to be wiped
PARISH_TABLES_TO_WIPE = [
    "baptisms",
    "confirmations",
    "first_communions",
    "marriages",
    "death_register",
    "pending_actions",
    "youth_profiles",
    "youth_action_plans",
    "parish_finances"
]

# The global tables in the public schema that need to be wiped
PUBLIC_TABLES_TO_WIPE = [
    "global_registry_index",
    "audit_logs"
]


async def execute_clean_slate():
    print("⚠️ INITIATING DIOCESE-WIDE CLEAN SLATE PROTOCOL...")
    print("Preserving Users and Infrastructure. Wiping all Sacramental and Audit data.\n")

    async with engine.connect() as conn:
        # 1. WIPE GLOBAL PUBLIC TABLES
        print("🌍 Clearing Global Indexes and Diocesan Audit Ledgers...")
        for table in PUBLIC_TABLES_TO_WIPE:
            # Using CASCADE safely handles any rogue foreign key constraints
            await conn.execute(text(f'TRUNCATE TABLE public.{table} CASCADE;'))
            print(f"  ✅ public.{table} wiped.")

        # 2. FETCH ALL TENANT SCHEMAS
        result = await conn.execute(text("SELECT name, schema_name FROM public.parishes"))
        parishes = result.fetchall()

        # 3. WIPE EACH PARISH SCHEMA
        print(f"\n🔄 Purging transactional data across {len(parishes)} isolated parish schemas...")
        for parish_name, schema_name in parishes:
            print(f"  Cleaning [{schema_name}] for {parish_name}...")

            try:
                # Switch connection to the specific parish's schema
                await conn.execute(text(f'SET search_path TO "{schema_name}"'))

                for table in PARISH_TABLES_TO_WIPE:
                    # We check if the table exists to prevent crashes if a migration was missed
                    await conn.execute(text(f"""
                        DO $$ 
                        BEGIN
                            IF EXISTS (SELECT FROM pg_tables WHERE schemaname = '{schema_name}' AND tablename = '{table}') THEN
                                EXECUTE 'TRUNCATE TABLE "{schema_name}".{table} CASCADE;';
                            END IF;
                        END $$;
                    """))

            except Exception as e:
                print(f"  ❌ Error wiping [{schema_name}]: {e}")

        # 4. COMMIT THE DESTRUCTION
        await conn.commit()

    print("\n🏁 Clean Slate Protocol Complete. The registers are officially empty.")
    await engine.dispose()


if __name__ == "__main__":
    # A simple safety catch so you don't accidentally run this in production later!
    confirm = input("Are you absolutely sure you want to wipe all testing data? (type 'yes'): ")
    if confirm.lower() == 'yes':
        asyncio.run(execute_clean_slate())
    else:
        print("Protocol aborted.")