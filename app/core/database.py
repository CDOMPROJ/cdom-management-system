from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Replace with your actual database password
DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/cdom_db"

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create the session maker that we will yield to our API routes
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)