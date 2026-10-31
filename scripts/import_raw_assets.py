"""Import every supplied RAW JPEG, retaining originals and building web-ready copies."""

import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps


SOURCE = Path("/Users/georgemollel/Desktop/raw")
IMAGE_ROOT = Path(__file__).resolve().parents[1] / "store" / "static" / "store" / "images" / "source-library"
ORIGINALS = IMAGE_ROOT / "originals"
WEB = IMAGE_ROOT / "webp"
MANIFEST = Path(__file__).resolve().parents[1] / "store" / "gallery_assets.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_SOURCE = SOURCE / "WhatsApp Video 2026-10-31 at 12.52.14.mp4"
VIDEO_TARGET = PROJECT_ROOT / "store" / "static" / "store" / "video" / "raw-campaign.mp4"

WOMEN = {19, 20, 23, 29, 36, 37, 38, 42, 43, 57, 78}
CAMPAIGN = {26, 28, 30, 58, 63, 80}


def main():
    files = sorted(SOURCE.glob("*.jpeg"))
    if not files:
        raise SystemExit(f"No JPEG files found in {SOURCE}")
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    manifest = []
    for number, source in enumerate(files, 1):
        original_name = f"{number:03d}-{source.name}"
        original_path = ORIGINALS / original_name
        web_path = WEB / f"image-{number:03d}.webp"
        shutil.copy2(source, original_path)
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
            image.save(web_path, "WEBP", quality=84, method=6)
        collection = (
            "women" if number in WOMEN else
            "campaign" if number in CAMPAIGN else
            "men"
        )
        manifest.append({
            "number": number,
            "source_filename": source.name,
            "original": str(original_path.relative_to(IMAGE_ROOT.parent.parent.parent)),
            "src": str(web_path.relative_to(IMAGE_ROOT.parent.parent.parent)),
            "collection": collection,
            "alt": f"RAW {collection} collection photograph {number:02d}",
        })
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if VIDEO_SOURCE.exists():
        VIDEO_TARGET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(VIDEO_SOURCE, VIDEO_TARGET)
    logo_source = PROJECT_ROOT / "store" / "static" / "store" / "images" / "raw-logo-original.jpeg"
    with Image.open(logo_source) as opened:
        logo = ImageOps.exif_transpose(opened).convert("RGB")
        for size in (192, 512):
            canvas = Image.new("RGB", (size, size), "white")
            mark = ImageOps.contain(logo, (size - 18, size - 18), Image.Resampling.LANCZOS)
            canvas.paste(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
            canvas.save(PROJECT_ROOT / "store" / "static" / "store" / "images" / f"raw-app-icon-{size}.png", optimize=True)
    print(f"Imported {len(files)} original photographs and generated {len(files)} WebP display assets.")
    if VIDEO_TARGET.exists():
        print(f"Campaign video: {VIDEO_TARGET} ({VIDEO_TARGET.stat().st_size:,} bytes)")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
