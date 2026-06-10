import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://kharcha:kharcha@localhost:5432/kharcha"

_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def db_session():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = _TestSession()

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    await session.close()

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    app.dependency_overrides.clear()
