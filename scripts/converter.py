from __future__ import annotations

import base64
import gzip
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image
from rlottie_python import LottieAnimation

log = logging.getLogger("gifts.converter")

ROOT = Path(__file__).resolve().parents[1]
TGS_DIR = ROOT / "assets" / "tgs"
PNG_DIR = ROOT / "assets" / "png"
WEBP_DIR = ROOT / "assets" / "webp"
SVG_DIR = ROOT / "assets" / "svg"


def _validate_tgs(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or "layers" not in data:
        raise ValueError(f"{path.name} is not a valid Lottie/TGS animation")
    return data


def convert_one(tgs_path: Path, size: tuple[int, int] = (256, 256)) -> dict:
    _validate_tgs(tgs_path)
    stem = tgs_path.stem
    png_path = PNG_DIR / f"{stem}.png"
    webp_path = WEBP_DIR / f"{stem}.webp"
    svg_path = SVG_DIR / f"{stem}.svg"

    # Render once; use the exact same preview for PNG, WebP and SVG.
    animation = LottieAnimation.from_tgs(str(tgs_path))
    image = animation.render_pillow_frame(
        frame_num=0, width=size[0], height=size[1]
    )
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    PNG_DIR.mkdir(parents=True, exist_ok=True)
    WEBP_DIR.mkdir(parents=True, exist_ok=True)
    SVG_DIR.mkdir(parents=True, exist_ok=True)

    image.save(png_path, "PNG", optimize=True)
    image.save(webp_path, "WEBP", quality=88, method=6)

    # Valid standalone SVG preview. The image itself is raster data embedded
    # in an SVG wrapper; it is not a path-based/vectorized Lottie conversion.
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size[0]}" height="{size[1]}" '
        f'viewBox="0 0 {size[0]} {size[1]}">'
        f'<image width="{size[0]}" height="{size[1]}" '
        f'href="data:image/png;base64,{encoded}"/>'
        '</svg>'
    )
    svg_path.write_text(svg, encoding="utf-8")

    return {
        "id": int(stem.removeprefix("gift_")),
        "filename": stem,
        "tgs": f"assets/tgs/{tgs_path.name}",
        "png": f"assets/png/{png_path.name}",
        "webp": f"assets/webp/{webp_path.name}",
        "svg": f"assets/svg/{svg_path.name}",
        "size": tgs_path.stat().st_size,
    }


def convert_all(max_workers: int = 4) -> list[dict]:
    files = sorted(TGS_DIR.glob("*.tgs"))
    if not files:
        log.warning("No TGS files found in %s", TGS_DIR)
        return []

    results: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(convert_one, path): path for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
                log.exception("Failed to convert %s", path.name)

    if errors:
        raise RuntimeError(
            "One or more conversions failed:\n" + "\n".join(errors)
        )
    return sorted(results, key=lambda item: item["id"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Converted {len(convert_all())} TGS files")
