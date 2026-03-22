import asyncio
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

# Assuming you have a standard database setup in app.core.database
from app.core.database import async_session_maker 
from app.models.all_models import (
    ParishModel, 
    DiocesanAnalyticsModel,
    BaptismModel,
    FirstCommunionModel,
    ConfirmationModel,
    MarriageModel,
    DeathRegisterModel,
    DiocesanContributionModel
)

async def run_diocesan_etl():
    print(f"[{datetime.now()}] 🚀 Starting Nightly Diocesan ETL Aggregation...")
    
    current_year = datetime.utcnow().year
    today = date.today()

    async with async_session_maker() as db:
        # 1. Fetch all active parishes from the Public schema
        parish_query = await db.execute(select(ParishModel))
        parishes = parish_query.scalars().all()
        
        if not parishes:
            print("No parishes found in the database. Exiting.")
            return

        print(f"Found {len(parishes)} parishes. Processing data for year {current_year}...")

        # 2. Loop through every parish to extract their yearly totals
        for parish in parishes:
            try:
                # Switch to the specific Parish's Tenant Schema
                await db.execute(text(f'SET search_path TO "{parish.schema_name}"'))
                
                # EXTRACT: Get the highest numbers for the current year
                # Note: We use the exact columns we designed to reset yearly
                b_query = await db.execute(select(func.max(BaptismModel.sequential_number)).where(BaptismModel.registry_year == current_year))
                baptisms_total = b_query.scalar() or 0
                
                c1_query = await db.execute(select(func.max(FirstCommunionModel.row_number)).where(FirstCommunionModel.registry_year == current_year))
                communions_total = c1_query.scalar() or 0
                
                c2_query = await db.execute(select(func.max(ConfirmationModel.row_number)).where(ConfirmationModel.registry_year == current_year))
                confirmations_total = c2_query.scalar() or 0
                
                m_query = await db.execute(select(func.max(MarriageModel.row_number)).where(MarriageModel.registry_year == current_year))
                marriages_total = m_query.scalar() or 0
                
                d_query = await db.execute(select(func.max(DeathRegisterModel.row_number)).where(DeathRegisterModel.registry_year == current_year))
                deaths_total = d_query.scalar() or 0
                
                # EXTRACT: Sum the financial targets and actuals for CDOM Obligations
                fin_query = await db.execute(
                    select(
                        func.sum(DiocesanContributionModel.target_amount),
                        func.sum(DiocesanContributionModel.actual_amount)
                    ).where(DiocesanContributionModel.reporting_year == current_year)
                )
                fin_result = fin_query.first()
                target_total = fin_result[0] or 0.00
                actual_total = fin_result[1] or 0.00

                # TRANSFORM & LOAD: Switch back to the Public schema to save the analytics
                await db.execute(text('SET search_path TO "public"'))
                
                # Check if an analytics row already exists for this parish
                analytics_query = await db.execute(
                    select(DiocesanAnalyticsModel).where(DiocesanAnalyticsModel.parish_id == parish.id)
                )
                analytics_record = analytics_query.scalar_one_or_none()
                
                if analytics_record:
                    # Update existing record
                    analytics_record.total_baptisms_ytd = baptisms_total
                    analytics_record.total_communions_ytd = communions_total
                    analytics_record.total_confirmations_ytd = confirmations_total
                    analytics_record.total_marriages_ytd = marriages_total
                    analytics_record.total_deaths_ytd = deaths_total
                    analytics_record.diocesan_contributions_target_ytd = target_total
                    analytics_record.diocesan_contributions_actual_ytd = actual_total
                    analytics_record.last_updated = today
                else:
                    # Create new record for this parish
                    new_analytics = DiocesanAnalyticsModel(
                        parish_id=parish.id,
                        parish_name=parish.name,
                        last_updated=today,
                        total_baptisms_ytd=baptisms_total,
                        total_communions_ytd=communions_total,
                        total_confirmations_ytd=confirmations_total,
                        total_marriages_ytd=marriages_total,
                        total_deaths_ytd=deaths_total,
                        diocesan_contributions_target_ytd=target_total,
                        diocesan_contributions_actual_ytd=actual_total
                    )
                    db.add(new_analytics)
                
                # Commit the transaction for this specific parish
                await db.commit()
                print(f"  ✅ Successfully aggregated data for: {parish.name}")

            except Exception as e:
                # If one parish fails (e.g., missing schema), roll back and continue to the next
                await db.rollback()
                print(f"  ❌ Error processing {parish.name}: {str(e)}")

    print(f"[{datetime.now()}] 🎉 Nightly ETL Aggregation Complete.")

if __name__ == "__main__":
    # Run the async script
    asyncio.run(run_diocesan_etl())