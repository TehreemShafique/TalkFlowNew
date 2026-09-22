import asyncio

from app.core.database import async_session_factory
from app.modules.auth.service import authenticate_user


async def check():
    async with async_session_factory() as db:
        u = await authenticate_user(db, "admin@phonova.io", "admin123")
        if u:
            print("AUTHENTICATION SUCCESSFUL FOR admin@phonova.io!")
        else:
            print("AUTHENTICATION FAILED!")


asyncio.run(check())
