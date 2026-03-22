import asyncio
import sys
import os

# Add the backend directory to the path so we can import our models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text, select
from passlib.context import CryptContext

from app.models.all_models import DeaneryModel, ParishModel, User

# Update with your actual password
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_database():
    print("🌱 Bootstrapping the Diocesan Database...")
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        # 1. Check/Create the Cathedral Deanery
        result = await db.execute(select(DeaneryModel).where(DeaneryModel.name == "Mansa Central Deanery"))
        new_deanery = result.scalar_one_or_none()

        if not new_deanery:
            new_deanery = DeaneryModel(name="Mansa Central Deanery")
            db.add(new_deanery)
            await db.commit()
            await db.refresh(new_deanery)
            print(f"✅ Created Deanery: {new_deanery.name}")
        else:
            print(f"⚡ Deanery '{new_deanery.name}' already exists. Skipping.")

        # 2. Check/Create the Cathedral Parish
        schema_name = "parish_mansa_cathedral"
        result = await db.execute(select(ParishModel).where(ParishModel.schema_name == schema_name))
        new_parish = result.scalar_one_or_none()

        if not new_parish:
            new_parish = ParishModel(
                name="Mansa Cathedral",
                deanery_id=new_deanery.id,
                schema_name=schema_name
            )
            db.add(new_parish)
            await db.commit()
            await db.refresh(new_parish)
            print(f"✅ Created Parish: {new_parish.name}")
        else:
            print(f"⚡ Parish '{new_parish.name}' already exists. Skipping.")

        # 3. Build the Physical Tenant Schema for the Cathedral
        await db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        await db.commit()
        print(f"✅ Verified Isolated Tenant Schema: {schema_name}")

        # 4. Check/Create Your Master Admin Account
        admin_email = "admin@mansadiocese.org"
        result = await db.execute(select(User).where(User.email == admin_email))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            hashed_password = pwd_context.hash("admin123")
            admin_user = User(
                email=admin_email,
                password_hash=hashed_password,
                role="SysAdmin",
                office="Curia",
                is_active=True
            )
            db.add(admin_user)
            await db.commit()
            print(f"✅ Created SysAdmin Account: {admin_user.email} (Password: admin123)")
        else:
            print(f"⚡ SysAdmin '{admin_user.email}' already exists. Skipping.")

    print("🎉 Database successfully seeded! The system is ready.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())