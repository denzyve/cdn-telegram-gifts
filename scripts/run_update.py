from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

from downloader import StarGiftsDownloader  # noqa: E402
from converter import convert_all  # noqa: E402
from catalog import write_catalog  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("gifts.update")


def get_existing_gifts() -> set[int]:
    gifts_dir = ROOT_DIR / "assets" / "tgs"

    if not gifts_dir.exists():
        return set()

    result = set()

    for path in gifts_dir.glob("gift_*.tgs"):
        try:
            result.add(int(path.stem.removeprefix("gift_")))
        except ValueError:
            log.warning("Unexpected gift filename: %s", path.name)

    return result


def set_github_output(new_gifts: bool, count: int) -> None:
    """Pass new gift information to GitHub Actions."""
    output_file = os.getenv("GITHUB_OUTPUT")

    if not output_file:
        log.info(
            "GitHub Actions output unavailable; "
            "new gifts: %s, count: %d",
            new_gifts,
            count,
        )
        return

    with open(output_file, "a", encoding="utf-8") as file:
        file.write(f"new_gifts={'true' if new_gifts else 'false'}\n")
        file.write(f"new_gifts_count={count}\n")


async def main() -> None:
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError("TG_API_ID and TG_API_HASH are required")

    # Remember gifts that existed before this update.
    existing_gifts = get_existing_gifts()

    downloader = StarGiftsDownloader(int(api_id), api_hash)
    download_result = await downloader.run()

    # Detect newly downloaded gifts.
    current_gifts = get_existing_gifts()
    added_gifts = current_gifts - existing_gifts

    new_gifts = len(added_gifts) > 0

    log.info(
        "New gifts detected: %d",
        len(added_gifts),
    )

    set_github_output(new_gifts, len(added_gifts))

    converted = convert_all(
        max_workers=int(os.getenv("CONVERTER_WORKERS", "4"))
    )

    write_catalog(download_result, converted)

    log.info(
        "Update complete: %d catalog entries; "
        "%d unsupported/no-sticker gifts skipped",
        len(converted),
        download_result.get("skipped", 0),
    )


if __name__ == "__main__":
    asyncio.run(main())
