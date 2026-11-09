import asyncpg

from app.core.config import settings


def test_config():
    assert settings.DATABASE_URL != ""
    assert settings.SECRET_KEY != ""
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    print(settings.DATABASE_URL)

async def test_tables():
    conn = await asyncpg.connect(settings.DATABASE_URL)

    tables = await conn.fetch("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
    """)
    print("Tables:", [t['tablename'] for t in tables])

    await conn.close()

test_config()
#asyncio.run(test_tables())
