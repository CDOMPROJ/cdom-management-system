# ==========================================
# CDOM Backend – Database Session Management
# ==========================================
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

# ==========================================
# Async Engine & Session Factory
# ==========================================
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,                    # Set to True only during debugging
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# ==========================================
# FastAPI Dependency
# ==========================================
async def get_db():
    """Yield an async database session for dependency injection in FastAPI routers."""
    async with AsyncSessionLocal() as session:
        yield session