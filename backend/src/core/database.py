from collections.abc import AsyncGenerator

import asyncpg

from src.core.config import settings


class Database:
    pool: asyncpg.Pool

    def __init__(self):
        pass
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=20
        )

    async def disconnect(self):
        await self.pool.close()

    async def acquire(self) -> AsyncGenerator[asyncpg.pool.PoolConnectionProxy, None]:
        async with self.pool.acquire() as conn:
            yield conn

db = Database()
