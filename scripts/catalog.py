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


def _without_last_seen(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "last_seen"}


def write_catalog(
    download_result: dict[str, Any],
    converted: list[dict[str, Any]],
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = _now()

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

    archived: dict[int, dict[str, Any]] = {
        int(item["id"]): dict(item)
        for item in old_catalog.get("gifts", [])
        if "id" in item
    }

    metadata_by_id = {
        int(item["id"]): item.get("metadata", {})
        for item in download_result.get("gifts", [])
    }

    for item in converted:
        gift_id = int(item["id"])
        previous = archived.get(gift_id, {})

        gift = {**previous, **item}
        gift["id"] = gift_id
        gift["first_seen"] = previous.get("first_seen", now)

        current_metadata = metadata_by_id.get(gift_id)
        gift["metadata"] = (
            current_metadata
            if current_metadata
            else previous.get("metadata", {})
        )

        # Update last_seen only when this gift's archived data changes.
        if not previous or _without_last_seen(gift) != _without_last_seen(previous):
            gift["last_seen"] = now
        else:
            gift["last_seen"] = previous.get("last_seen", now)

        archived[gift_id] = gift

    gifts = sorted(archived.values(), key=lambda item: int(item["id"]))

    # Compare the actual catalog content, excluding its update timestamp.
    old_gifts = old_catalog.get("gifts", [])
    catalog_changed = gifts != old_gifts

    updated_at = now if catalog_changed else old_catalog.get("updated_at", now)

    catalog = {
        "schema_version": 2,
        "updated_at": updated_at,
        "count": len(gifts),
        "gifts": gifts,
    }

    stats = {
        "updated_at": updated_at,
        "total_gifts": len(gifts),
        "formats": {
            "tgs": len(gifts),
            "png": len(gifts),
            "webp": len(gifts),
            "svg": len(gifts),
        },
    }

    new_catalog_text = json.dumps(
        catalog, ensure_ascii=False, indent=2
    ) + "\n"
    new_stats_text = json.dumps(
        stats, ensure_ascii=False, indent=2
    ) + "\n"

    # Avoid rewriting files when their contents are unchanged.
    if (
        not CATALOG_PATH.exists()
        or CATALOG_PATH.read_text(encoding="utf-8") != new_catalog_text
    ):
        CATALOG_PATH.write_text(new_catalog_text, encoding="utf-8")

    if (
        not STATS_PATH.exists()
        or STATS_PATH.read_text(encoding="utf-8") != new_stats_text
    ):
        STATS_PATH.write_text(new_stats_text, encoding="utf-8")