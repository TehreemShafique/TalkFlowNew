import asyncio
from sqlalchemy import select
from app.core.config import settings
from app.core.database import async_session_factory
from app.packages.db.models import Campaign, Lead

async def check():
    print(f"DATABASE_URL: {settings.database_url}")
    print(f"REDIS_URL: {settings.redis_url}")
    async with async_session_factory() as db:
        res = await db.execute(select(Campaign))
        campaigns = res.scalars().all()
        print(f"TOTAL CAMPAIGNS IN DB: {len(campaigns)}")
        for c in campaigns:
            print(f" - ID: {c.id} | Name: {c.name} | Status: {c.status} | CreatedAt: {c.created_at}")
            
        res_leads = await db.execute(select(Lead))
        leads = res_leads.scalars().all()
        print(f"TOTAL LEADS IN DB: {len(leads)}")
        for l in leads[:5]:
            print(f" - ID: {l.id} | Name: {l.first_name} {l.last_name} | Phone: {l.phone_raw}")

if __name__ == "__main__":
    asyncio.run(check())
