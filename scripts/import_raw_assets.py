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
    print(f"Imported {len(files)} original photographs and generated {len(files)} WebP display assets.")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
