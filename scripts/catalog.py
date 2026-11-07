from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CATALOG_PATH = DATA_DIR / "gifts.json"
STATS_PATH = DATA_DIR / "stats.json"


def write_catalog(download_result: dict, converted: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    metadata_by_id = {
        int(item["id"]): item.get("metadata", {})
        for item in download_result.get("gifts", [])
    }

    gifts = []
    for item in converted:
        gift = dict(item)
        gift["metadata"] = metadata_by_id.get(int(item["id"]), {})
        gifts.append(gift)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    catalog = {
        "schema_version": 1,
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
