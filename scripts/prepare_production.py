import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import sys
import os

# Ensure the app module can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal


async def wipe_transactional_data():
    """Wipes all test records. Skips tables that haven't been migrated yet."""
    print("Initiating Production Data Cleanse...")

    tables_to_wipe = [
        "audit_logs",
        "pending_actions",
        "action_plan_communications",
        "youth_action_plans",
        "youth_profiles",
        "diocesan_contributions",
        "parish_finances",
        "global_registry_index",
        "death_register",
        "marriages",
        "confirmations",
        "first_communions",
        "baptisms",
        "diocesan_analytics"
    ]

    async with AsyncSessionLocal() as session:
        for table in tables_to_wipe:
            try:
                # We use a nested transaction (SAVEPOINT) so if one table fails
                # (because it doesn't exist), it doesn't crash the whole script.
                async with session.begin_nested():
                    await session.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
                    print(f"  [-] Wiped {table}")
            except Exception:
                print(f"  [~] Skipped {table} (Table does not exist yet)")

        await session.commit()
        print("\n✅ Database successfully prepped. You may now run migrations.")


if __name__ == "__main__":
    asyncio.run(wipe_transactional_data())