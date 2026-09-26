import asyncio

from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.packages.db.models import Lead


async def inspect():
    async with async_session_factory() as db:
        res = await db.execute(
            select(Lead.source, Lead.source_batch_id, func.count(Lead.id)).group_by(
                Lead.source, Lead.source_batch_id
            )
        )
        groups = res.all()
        print("LEAD SOURCE BREAKDOWN:")
        for source, batch_id, count in groups:
            print(f" - Source: {source} | Batch: {batch_id} | Count: {count}")

        sample_lead = (await db.execute(select(Lead).limit(1))).scalar_one_or_none()
        if sample_lead:
            print("\nSample Lead details:")
            print(f" - ID: {sample_lead.id}")
            print(f" - Name: {sample_lead.first_name} {sample_lead.last_name}")
            print(f" - Phone: {sample_lead.phone_raw}")
            print(f" - Source: {sample_lead.source}")


if __name__ == "__main__":
    asyncio.run(inspect())
