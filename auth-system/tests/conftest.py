import asyncio
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Switch environment to testing prior to any configuration imports
import os
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_auth_system.db"
# Force the mocked payout/payment path regardless of what's in the developer's real .env -
# tests must never depend on (or accidentally exercise) a real Paystack key.
os.environ["PAYSTACK_SECRET_KEY"] = ""

# Import app, settings, and db dependencies
from app.main import app
from app.core.config import settings
from app.core.database import get_async_db, Base

# Setup clean test engine
test_engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True
)

test_async_session_maker = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Drops and re-creates testing schema tables for each clean test run."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session instance for direct seed manipulation in tests."""
    async with test_async_session_maker() as session:
        yield session

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yields an AsyncClient for calling test requests against the FastAPI app."""
    # Override database dependency injection
    async def override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_async_db] = override_get_async_db
    
    # Disable rate limiting for the duration of tests
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False

    # Initialize the client with standard HTTP Transport
    # ASGI Transport allows direct calling of mock routes without network roundtrips
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://testserver"
    ) as async_client:
        yield async_client
        
    # Clear overrides at the end of the test execution
    app.dependency_overrides.clear()
