import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def check():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        res_jobs = await conn.execute(
            text("SELECT id, file_name, total_rows, created_at FROM lead_import_jobs")
        )
        jobs = res_jobs.fetchall()
        print("=== LEAD IMPORT JOBS IN DATABASE ===")
        print(f"Total jobs in DB: {len(jobs)}")
        for j in jobs:
            print(f"Job ID: {j[0]} | File: {j[1]} | Rows: {j[2]}")

        res_leads = await conn.execute(
            text("SELECT count(*), source FROM leads GROUP BY source")
        )
        leads_summary = res_leads.fetchall()
        print("\n=== LEADS SUMMARY BY SOURCE IN DATABASE ===")
        for s in leads_summary:
            print(f"Count: {s[0]} | Source: {s[1]}")


if __name__ == "__main__":
    asyncio.run(check())
