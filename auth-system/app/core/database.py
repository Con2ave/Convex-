from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Determine if we are using SQLite to configure check_same_thread if needed
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# Create the async db engine
# echo=True can be enabled for SQL query profiling in development/debugging
engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
    echo=False
)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Modern SQLAlchemy 2.0 Base Declarative Class
class Base(DeclarativeBase):
    pass

# FastAPI Dependency to yield database sessions per request
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
