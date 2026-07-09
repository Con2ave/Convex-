from typing import AsyncGenerator
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

db_url = settings.SQLALCHEMY_DATABASE_URL
is_sqlite = db_url.startswith("sqlite")
is_postgres = db_url.startswith("postgresql")

# SQLite needs check_same_thread off for async use; hosted Postgres (Neon, Render, Supabase,
# ...) requires SSL and won't accept plaintext connections - local Postgres typically doesn't.
connect_args = {}
if is_sqlite:
    connect_args = {"check_same_thread": False}
elif is_postgres and urlparse(db_url).hostname not in ("localhost", "127.0.0.1"):
    connect_args = {"ssl": "require"}

# Create the async db engine
# echo=True can be enabled for SQL query profiling in development/debugging
engine = create_async_engine(
    db_url,
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
