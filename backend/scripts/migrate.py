import asyncio
import asyncpg
from pathlib import Path
from app.core.config import settings

async def run_migrations():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    for migration in sorted(migrations_dir.glob("*.sql")):
        print(f"Running {migration.name}")
        sql = migration.read_text()
        await conn.execute(sql)
    
    await conn.close()
    print("Done")

asyncio.run(run_migrations())