from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from hydrogram import Client
from hydrogram.raw import functions, types

log = logging.getLogger("gifts.downloader")


def _is_tgs(document: Any) -> bool:
    """Accept Telegram animated-sticker documents; do not guess from file size."""
    mime = (getattr(document, "mime_type", "") or "").lower()
    return mime in {
        "application/x-tgsticker",
        "application/x-tgsdice",
        "application/x-tgsticker+json",
    }


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value]
    return str(value)


class StarGiftsDownloader:
    def __init__(self, api_id: int, api_hash: str, session_name: str = "stars_gifts"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.tgs_dir = Path("assets/tgs")

    def _client(self) -> Client:
        session_string = os.getenv("HYDROGRAM_SESSION_STRING")
        if session_string:
            return Client(
                self.session_name,
                api_id=self.api_id,
                api_hash=self.api_hash,
                session_string=session_string,
                no_updates=True,
            )
        # Local development
        return Client(
            self.session_name,
            api_id=self.api_id,
            api_hash=self.api_hash,
            workdir=".",
            no_updates=True,
        )

    async def run(self) -> dict[str, Any]:
        self.tgs_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[dict[str, Any]] = []
        skipped = 0

        async with self._client() as app:
            result = await app.invoke(functions.payments.GetStarGifts(hash=0))

            if not hasattr(result, "gifts"):
                raise RuntimeError(
                    f"Unexpected Telegram response: {type(result).__name__}"
                )

            gifts = result.gifts
            log.info("Telegram returned %d gifts", len(gifts))

            for gift in gifts:
                document = getattr(gift, "sticker", None)
                if document is None or not isinstance(document, types.Document):
                    skipped += 1
                    continue
                if not _is_tgs(document):
                    log.warning(
                        "Skipping gift %s: unsupported sticker MIME type %r",
                        getattr(gift, "id", "?"),
                        getattr(document, "mime_type", None),
                    )
                    skipped += 1
                    continue

                gift_id = int(gift.id)
                filename = f"gift_{gift_id}.tgs"
                target = self.tgs_dir / filename

                if not target.exists() or target.stat().st_size != int(document.size):
                    await self._download_document(app, document, target)

                downloaded.append({
                    "id": gift_id,
                    "filename": filename,
                    "mime_type": getattr(document, "mime_type", None),
                    "size": int(getattr(document, "size", 0) or 0),
                    "metadata": self._gift_metadata(gift),
                })

        log.info(
            "Download pass complete: %d supported gifts, %d skipped",
            len(downloaded), skipped
        )
        return {"gifts": downloaded, "skipped": skipped}

    @staticmethod
    def _gift_metadata(gift: Any) -> dict[str, Any]:
        # Keep only simple Telegram fields; avoid serializing raw TL objects.
        candidate_fields = (
            "id", "stars", "availability_remains", "availability_total",
            "limited", "sold_out", "birthday", "upgrade_stars",
            "convert_stars", "first_sale_date", "last_sale_date",
        )
        data: dict[str, Any] = {}
        for field in candidate_fields:
            if hasattr(gift, field):
                data[field] = _safe_value(getattr(gift, field))
        return data

    async def _download_document(self, app: Client, document: Any, target: Path) -> None:
        location = types.InputDocumentFileLocation(
            id=document.id,
            access_hash=document.access_hash,
            file_reference=document.file_reference,
            thumb_size="",
        )
        expected_size = int(getattr(document, "size", 0) or 0)
        chunk_size = 512 * 1024
        offset = 0
        temporary = target.with_suffix(target.suffix + ".part")

        try:
            with temporary.open("wb") as output:
                while expected_size == 0 or offset < expected_size:
                    response = await app.invoke(
                        functions.upload.GetFile(
                            location=location,
                            offset=offset,
                            limit=chunk_size,
                            precise=False,
                            cdn_supported=True,
                        )
                    )

                    # Telegram may return a CDN redirect instead of file bytes.
                    # Never treat that response as an empty/successful download.
                    if not hasattr(response, "bytes"):
                        raise RuntimeError(
                            "Telegram returned a non-file response "
                            f"({type(response).__name__}); CDN redirect handling "
                            "is required for this document."
                        )

                    chunk = response.bytes
                    if not chunk:
                        break

                    output.write(chunk)
                    offset += len(chunk)

                    if len(chunk) < chunk_size:
                        break

            if not temporary.exists() or temporary.stat().st_size == 0:
                raise RuntimeError("Telegram returned an empty document")
            if expected_size and temporary.stat().st_size != expected_size:
                raise RuntimeError(
                    f"Incomplete download: expected {expected_size} bytes, "
                    f"received {temporary.stat().st_size}"
                )

            # Verify that the downloaded file is gzip-compressed TGS JSON.
            import gzip
            import json
            with gzip.open(temporary, "rt", encoding="utf-8") as stream:
                parsed = json.load(stream)
            if not isinstance(parsed, dict):
                raise RuntimeError("TGS payload is not a JSON object")

            temporary.replace(target)
            log.info("Downloaded %s (%d bytes)", target.name, target.stat().st_size)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


async def async_main() -> dict[str, Any]:
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("Set TG_API_ID and TG_API_HASH environment variables")
    return await StarGiftsDownloader(int(api_id), api_hash).run()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(async_main())
