from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

# 1. Securely pull the URL from the environment variables, NEVER hardcode it.
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# 2. Create the session maker
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)