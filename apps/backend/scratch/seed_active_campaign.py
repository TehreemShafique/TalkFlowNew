import asyncio
from sqlalchemy import select

from app.core.database import async_session_factory
from app.packages.contracts.enums import CampaignStatus, LeadStatus
from app.packages.db.models import Campaign, Lead


async def seed():
    async with async_session_factory() as db:
        # Check if an active campaign exists
        res = await db.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE.value).limit(1)
        )
        campaign = res.scalar_one_or_none()

        if not campaign:
            campaign = Campaign(
                name="Medicare Advantage 2026",
                status=CampaignStatus.ACTIVE.value,
            )
            db.add(campaign)
            await db.flush()
            print(f"CREATED_CAMPAIGN_ID: {campaign.id}")
        else:
            print(f"EXISTING_CAMPAIGN_ID: {campaign.id}")

        # Check if a lead exists
        res_lead = await db.execute(select(Lead).limit(1))
        lead = res_lead.scalar_one_or_none()
        if not lead:
            lead = Lead(
                first_name="John",
                last_name="Doe",
                phone_raw="+12025550134",
                phone_normalized="+12025550134",
                campaign_id=campaign.id,
                status=LeadStatus.NEW.value,
            )
            db.add(lead)
            await db.flush()
            print(f"CREATED_LEAD_ID: {lead.id}")
        else:
            print(f"EXISTING_LEAD_ID: {lead.id}")

        await db.commit()
        print("SEED_COMPLETE")


if __name__ == "__main__":
    asyncio.run(seed())
