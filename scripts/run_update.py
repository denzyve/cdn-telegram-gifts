from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

from downloader import StarGiftsDownloader  # noqa: E402
from converter import convert_all  # noqa: E402
from catalog import load_archived_ids, write_catalog  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("gifts.update")


def get_existing_tgs_ids() -> set[int]:
    gifts_dir = ROOT_DIR / "assets" / "tgs"
    result: set[int] = set()

    if not gifts_dir.exists():
        return result

    for path in gifts_dir.glob("gift_*.tgs"):
        try:
            result.add(int(path.stem.removeprefix("gift_")))
        except ValueError:
            log.warning("Ignoring unexpected filename: %s", path.name)

    return result


def set_github_output(new_gifts: bool, count: int) -> None:
    output_file = os.getenv("GITHUB_OUTPUT")
    if not output_file:
        return

    with open(output_file, "a", encoding="utf-8") as file:
        file.write(f"new_gifts={'true' if new_gifts else 'false'}\n")
        file.write(f"new_gifts_count={count}\n")


async def main() -> None:
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError("TG_API_ID and TG_API_HASH are required")

    # IDs already archived before this update.
    known_ids = load_archived_ids() | get_existing_tgs_ids()

    downloader = StarGiftsDownloader(int(api_id), api_hash)
    download_result = await downloader.run()

    converted = convert_all(
        max_workers=int(os.getenv("CONVERTER_WORKERS", "4"))
    )

    # New means an ID that has never been archived before.
    current_ids = {
        int(item["id"])
        for item in download_result.get("gifts", [])
    }
    new_ids = current_ids - known_ids

    write_catalog(download_result, converted)
    set_github_output(bool(new_ids), len(new_ids))

    log.info(
        "Update complete: %d catalog entries; "
        "%d new gifts; %d unsupported/no-sticker gifts skipped",
        len(converted),
        len(new_ids),
        download_result.get("skipped", 0),
    )


if __name__ == "__main__":
    asyncio.run(main())