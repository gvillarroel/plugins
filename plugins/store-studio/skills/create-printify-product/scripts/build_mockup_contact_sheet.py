from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a contact sheet from a sanitized Printify mockup manifest.",
    )
    parser.add_argument("--manifest", required=True, help="Input manifest JSON.")
    parser.add_argument("--output", required=True, help="Output contact sheet image.")
    parser.add_argument("--columns", type=int, default=4, help="Tile columns.")
    parser.add_argument("--thumb-size", type=int, default=260, help="Thumbnail box size.")
    return parser.parse_args()


def load_font(name: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def collect_entries(manifest: dict) -> list[tuple[str, dict, Path, Image.Image]]:
    entries = []
    for product in manifest["products"]:
        for image in product["images"]:
            file_path = Path(image["file"])
            with Image.open(file_path) as source:
                image["width"], image["height"] = source.size
                entries.append((product["title"], image.copy(), file_path, source.copy()))
    return entries


def build_contact_sheet(
    entries: list[tuple[str, dict, Path, Image.Image]],
    output: Path,
    columns: int,
    thumb_size: int,
) -> None:
    label_height = 58
    padding = 18
    rows = (len(entries) + columns - 1) // columns
    sheet_width = columns * thumb_size + (columns + 1) * padding
    sheet_height = rows * (thumb_size + label_height) + (rows + 1) * padding

    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")
    draw = ImageDraw.Draw(sheet)
    label_font = load_font("arial.ttf", 12)

    for index, (_title, metadata, file_path, source) in enumerate(entries):
        row, column = divmod(index, columns)
        x = padding + column * (thumb_size + padding)
        y = padding + row * (thumb_size + label_height + padding)

        image = source.convert("RGB")
        image.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
        image_x = x + (thumb_size - image.width) // 2
        image_y = y + (thumb_size - image.height) // 2
        sheet.paste(image, (image_x, image_y))
        draw.rectangle(
            [x, y, x + thumb_size, y + thumb_size],
            outline=(210, 210, 210),
            width=1,
        )

        colors = ", ".join(metadata.get("colors") or ["all colors"])
        filename = Path(file_path).name
        details = (
            f"{metadata.get('position')} | {colors} | "
            f"{metadata.get('width')}x{metadata.get('height')}"
        )
        draw.text((x, y + thumb_size + 6), filename[:42], fill=(20, 20, 20), font=label_font)
        draw.text((x, y + thumb_size + 26), details[:42], fill=(70, 70, 70), font=label_font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest)
    output = Path(args.output)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = collect_entries(manifest)

    build_contact_sheet(entries, output, args.columns, args.thumb_size)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"updated_manifest={manifest_path}")
    print(f"contact_sheet={output}")
    print(f"entries={len(entries)}")


if __name__ == "__main__":
    main()
