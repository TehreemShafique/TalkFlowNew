import asyncio
from app.core.database import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT count(*) FROM calls"))
        count = result.scalar()
        print("REAL_TOTAL_CALLS_IN_DATABASE:", count)

if __name__ == "__main__":
    asyncio.run(main())
