import asyncio
import sys
import os
import random
from faker import Faker
from datetime import date, timedelta
from sqlalchemy import select, func
from collections import defaultdict

# Ensure the app module can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.all_models import (
    BaptismModel, MarriageModel, FinanceModel,
    GlobalRegistryIndex, ReligionCategory, TransactionType,
    IncomeCategory, ExpenseCategory
)

fake = Faker()


def get_minister():
    """Requirement: Minister must have two names (e.g., Fr. First Last)."""
    return f"Fr. {fake.first_name_male()} {fake.last_name()}"


def get_random_date_since_2010():
    """Generates a random date from January 1, 2010 to today."""
    start_date = date(2010, 1, 1)
    end_date = date.today()
    days_between = (end_date - start_date).days
    random_days = random.randrange(days_between)
    return start_date + timedelta(days=random_days)


async def generate_massive_data():
    parish_targets = {
        1: 300,  # St. Mary
        2: 400,  # St. Christopher
        3: 500  # St. John Paul II
    }

    async with AsyncSessionLocal() as db:
        print("🚀 Initializing State-Aware Seeder (No Leading Zeros)...")

        # --- 1. FETCH CURRENT DATABASE STATE ---
        bap_state_query = await db.execute(
            select(BaptismModel.registry_year, func.max(BaptismModel.row_number)).group_by(BaptismModel.registry_year))
        bap_tracker = defaultdict(int, {row[0]: row[1] for row in bap_state_query.all()})

        mar_state_query = await db.execute(
            select(MarriageModel.registry_year, func.max(MarriageModel.row_number)).group_by(
                MarriageModel.registry_year))
        mar_tracker = defaultdict(int, {row[0]: row[1] for row in mar_state_query.all()})

        finance_row_counter = 1

        for parish_id, target_count in parish_targets.items():
            print(f"Generating {target_count} chronological records for Parish ID: {parish_id}...")

            # Generate dates in memory first so we can sort them chronologically
            raw_baptisms = [get_random_date_since_2010() for _ in range(target_count)]
            raw_baptisms.sort()

            for bap_date in raw_baptisms:
                year = bap_date.year

                # Increment the global tracker for this specific year
                bap_tracker[year] += 1
                row_num = bap_tracker[year]

                # Strict formatting rule: number/year (NO LEADING ZEROS)
                formatted_bap_no = f"{row_num}/{year}"

                baptism = BaptismModel(
                    first_name=fake.first_name(),
                    middle_name=fake.first_name() if random.random() > 0.5 else None,
                    last_name=fake.last_name(),
                    dob=bap_date - timedelta(days=random.randint(30, 180)),
                    village=fake.city(),
                    father_first_name=fake.first_name_male(),
                    father_last_name=fake.last_name(),
                    mother_first_name=fake.first_name_female(),
                    mother_last_name=fake.last_name(),
                    godparents=f"{fake.name()} and {fake.name()}",
                    date_of_baptism=bap_date,
                    minister_of_baptism=get_minister(),
                    registry_year=year,
                    row_number=row_num,
                    formatted_number=formatted_bap_no
                )
                db.add(baptism)

                # Link to Global Index
                db.add(GlobalRegistryIndex(
                    record_type="BAPTISM",
                    canonical_number=formatted_bap_no,
                    first_name=baptism.first_name,
                    last_name=baptism.last_name,
                    parish_id=parish_id
                ))

                # --- 2. GENERATE MARRIAGE (Approx 20% of the time) ---
                if random.random() < 0.2:
                    m_date = bap_date + timedelta(days=random.randint(1, 30))
                    m_year = m_date.year

                    mar_tracker[m_year] += 1
                    m_row_num = mar_tracker[m_year]

                    # Strict formatting rule: number/year (NO LEADING ZEROS)
                    formatted_mar_no = f"{m_row_num}/{m_year}"

                    marriage = MarriageModel(
                        groom_first_name=fake.first_name_male(),
                        groom_last_name=fake.last_name(),
                        groom_religion=random.choice(list(ReligionCategory)),
                        bride_first_name=fake.first_name_female(),
                        bride_last_name=fake.last_name(),
                        bride_religion=random.choice(list(ReligionCategory)),
                        marriage_date=m_date,
                        minister=get_minister(),
                        witness_1=fake.name(),
                        witness_2=fake.name(),
                        registry_year=m_year,
                        row_number=m_row_num,
                        formatted_number=formatted_mar_no
                    )
                    db.add(marriage)

                    db.add(GlobalRegistryIndex(
                        record_type="MARRIAGE",
                        canonical_number=formatted_mar_no,
                        first_name=f"{marriage.groom_first_name} & {marriage.bride_first_name}",
                        last_name="Marriage",
                        parish_id=parish_id
                    ))

                # --- 3. GENERATE FINANCES ---
                db.add(FinanceModel(
                    row_number=finance_row_counter,
                    transaction_date=bap_date,
                    transaction_type=TransactionType.INCOME,
                    category=random.choice(list(IncomeCategory)).value,
                    amount=round(random.uniform(100.0, 5000.0), 2),
                    recorded_by="System Auto-Seeder"
                ))
                finance_row_counter += 1

            # Commit batch per parish to ensure memory efficiency
            await db.commit()
            print(f"✅ Parish {parish_id} completely populated.")

        print("\n🎉 Seeding Complete! Canonical references perfectly formatted (e.g., 1/2010).")


if __name__ == "__main__":
    asyncio.run(generate_massive_data())