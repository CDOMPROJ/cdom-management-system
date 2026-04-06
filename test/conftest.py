import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.core.config import settings
from app.core.dependencies import get_db, require_create_access, require_read_access
from app.models.all_models import Base

# ====================================================================
# 1. FORCE A SINGLE EVENT LOOP FOR ALL TESTS
# ====================================================================
@pytest.fixture(scope="session")
def event_loop():
    """Forces pytest to use the same event loop for the entire session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ====================================================================
# 2. THE TEST DATABASE ENGINE
# ====================================================================
from sqlalchemy.pool import NullPool
from app.models.all_models import ParishModel  # Ensure we import the Parish Model

test_engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    # 1. Build the empty tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 2. Seed the database with Dummy Parish #1 to satisfy Foreign Keys
    async with TestingSessionLocal() as session:
        # Depending on your exact model, you might just need id and name.
        # Adjust kwargs here if your ParishModel requires more fields!
        dummy_parish = ParishModel(id=1, name="Test Parish")
        session.add(dummy_parish)
        await session.commit()

    yield  # Let the tests run!

    # 3. Tear down the database
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

# ====================================================================
# 3. INTERCEPT DEPENDENCIES
# ====================================================================
async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

async def override_auth():
    return {
        "user_id": 1,
        "parish_id": 1,
        "tenant_schema": "public",
        "role": "PARISH_PRIEST"
    }

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[require_create_access] = override_auth
app.dependency_overrides[require_read_access] = override_auth

# ====================================================================
# 4. HTTPX ASYNC CLIENT
# ====================================================================
@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client