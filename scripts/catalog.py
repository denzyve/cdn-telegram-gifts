from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CATALOG_PATH = DATA_DIR / "gifts.json"
STATS_PATH = DATA_DIR / "stats.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_archived_ids() -> set[int]:
    """Return gift IDs already known to the historical catalog."""
    if not CATALOG_PATH.exists():
        return set()

    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Cannot read existing catalog: {exc}") from exc

    return {
        int(item["id"])
        for item in catalog.get("gifts", [])
        if "id" in item
    }


def write_catalog(
    download_result: dict[str, Any],
    converted: list[dict[str, Any]],
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    now = _now()

    # Load the previous archive instead of rebuilding it from scratch.
    if CATALOG_PATH.exists():
        try:
            old_catalog = json.loads(
                CATALOG_PATH.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(
                f"Cannot read existing catalog: {exc}"
            ) from exc
    else:
        old_catalog = {}

    archived: dict[int, dict[str, Any]] = {}

    for item in old_catalog.get("gifts", []):
        gift_id = int(item["id"])
        archived[gift_id] = dict(item)

    metadata_by_id = {
        int(item["id"]): item.get("metadata", {})
        for item in download_result.get("gifts", [])
    }

    # Merge current conversions into the historical archive.
    for item in converted:
        gift_id = int(item["id"])
        previous = archived.get(gift_id, {})

        gift = {**previous, **item}
        gift["id"] = gift_id

        # Preserve the original first_seen date.
        gift["first_seen"] = previous.get("first_seen", now)

        # Update last_seen only for gifts returned by Telegram this run.
        gift["last_seen"] = now

        # Do not erase old metadata if the current response has none.
        current_metadata = metadata_by_id.get(gift_id)
        if current_metadata:
            gift["metadata"] = current_metadata
        else:
            gift["metadata"] = previous.get("metadata", {})

        archived[gift_id] = gift

    gifts = sorted(archived.values(), key=lambda item: int(item["id"]))

    catalog = {
        "schema_version": 2,
        "updated_at": now,
        "count": len(gifts),
        "gifts": gifts,
    }

    stats = {
        "updated_at": now,
        "total_gifts": len(gifts),
        "formats": {
            "tgs": len(gifts),
            "png": len(gifts),
            "webp": len(gifts),
            "svg": len(gifts),
        },
    }

    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    STATS_PATH.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )