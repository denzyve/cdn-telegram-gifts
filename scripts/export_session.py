"""Export the existing local Hydrogram session to a GitHub Actions secret.

Run this locally beside stars_gifts.session:
    TG_API_ID=... TG_API_HASH=... python scripts/export_session.py
The printed value is a credential. Never commit it or paste it into issues/chats.
"""
import asyncio
import os
from hydrogram import Client


async def main() -> None:
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH")
    async with Client(
        "stars_gifts",
        api_id=int(api_id),
        api_hash=api_hash,
        workdir=".",
        no_updates=True,
    ) as app:
        print(await app.export_session_string())


if __name__ == "__main__":
    asyncio.run(main())
