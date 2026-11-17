#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Prepare Slides requests for a link, image, or Drive video without uploading."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True

from slides_batch import Frame, NO_PAINT, OBJECT_ID, element_properties, solid_fill, text_requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slide-id", required=True, help="Existing slide ID, or a new ID with --create-slide.")
    parser.add_argument("--id-prefix", required=True, help="Unused prefix of 3 to 38 characters for media object IDs.")
    parser.add_argument("--create-slide", action="store_true", help="Create a blank slide in the batch.")
    parser.add_argument("--revision", help="Required revision ID from a fresh read of the target deck.")
    parser.add_argument("--page-size", nargs=2, type=float, default=(720, 405), metavar=("W", "H"),
                        help="Slide dimensions in points. Default is 720 by 405.")
    parser.add_argument("--output", type=Path, required=True, help="Slides batchUpdate JSON path.")
    parser.add_argument("--html-url", help="Authorized HTTP(S) URL for the original interactive HTML.")
    parser.add_argument("--link-frame", nargs=4, type=float, metavar=("X", "Y", "W", "H"),
                        help="Native link box in slide points. Required with --html-url.")
    parser.add_argument("--link-text", help="One-line link label. Default is 'Open interactive original'.")
    media = parser.add_mutually_exclusive_group()
    media.add_argument("--image-url", help="Publicly reachable PNG, JPEG, or GIF URL, up to 2 KB.")
    media.add_argument("--drive-video-id", help="File ID of a processed video in Google Drive.")
    parser.add_argument("--frame", nargs=4, type=float, metavar=("X", "Y", "W", "H"),
                        help="Media frame in slide points. Required with an image or video.")
    parser.add_argument("--video-size", nargs=2, type=int, metavar=("W", "H"),
                        help="Video dimensions in pixels. Required to preserve its aspect ratio.")
    parser.add_argument("--video-start", type=int, metavar="SECONDS", help="Start playback at a whole second.")
    parser.add_argument("--video-end", type=int, metavar="SECONDS", help="End playback at a whole second.")
    parser.add_argument("--autoplay", action="store_true", help="Start the video automatically in presentation mode.")
    parser.add_argument("--mute", action="store_true", help="Mute the video during playback.")
    parser.add_argument("--media-title", help="Alternative text title for the image or video.")
    parser.add_argument("--media-description", help="Alternative text description for the image or video.")
    return parser.parse_args()


def validate_url(value: str, label: str) -> None:
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{label} must be an HTTP(S) URL without whitespace.")
    url = urlsplit(value)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None:
        raise ValueError(f"{label} must be an absolute HTTP(S) URL without embedded credentials.")


def validate_frame(box: Frame, page_size: tuple[float, float], label: str) -> None:
    x, y, width, height = box
    if not all(map(math.isfinite, box)) or min(x, y) < 0 or min(width, height) <= 0:
        raise ValueError(f"{label} requires finite nonnegative origins and positive dimensions.")
    if x + width > page_size[0] + 1e-8 or y + height > page_size[1] + 1e-8:
        raise ValueError(f"{label} must fit the slide page.")


def video_frame(box: Frame, dimensions: tuple[int, int]) -> Frame:
    source_width, source_height = dimensions
    x, y, width, height = box
    scale = min(width / source_width, height / source_height)
    fitted_width = source_width * scale
    fitted_height = source_height * scale
    return x + (width - fitted_width) / 2, y + (height - fitted_height) / 2, fitted_width, fitted_height


def overlaps(a: Frame, b: Frame) -> bool:
    return all(
        min(a[axis] + a[axis + 2], b[axis] + b[axis + 2]) > max(a[axis], b[axis])
        for axis in (0, 1)
    )


def link_requests(slide_id: str, object_id: str, frame: Frame, label: str, url: str) -> list[dict]:
    text = text_requests({
        "text": label, "fill": "#6d1222", "fontFamily": "Arial",
        "fontSize": 12, "bold": True, "italic": False, "align": "center",
    }, object_id, 1)
    style = text[1]["updateTextStyle"]
    style["style"].update(link={"url": url}, underline=True)
    style["fields"] += ",link,underline"
    return [
        {"createShape": {
            "objectId": object_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": element_properties(slide_id, frame),
        }},
        {"updateShapeProperties": {
            "objectId": object_id,
            "shapeProperties": {
                "shapeBackgroundFill": solid_fill("#ffffff"),
                "outline": NO_PAINT,
                "contentAlignment": "MIDDLE",
                "autofit": {"autofitType": "NONE"},
            },
            "fields": "shapeBackgroundFill,outline,contentAlignment,autofit.autofitType",
        }},
        *text,
    ]


def video_properties(args: argparse.Namespace) -> dict:
    properties = {}
    if args.autoplay:
        properties["autoPlay"] = True
    if args.mute:
        properties["mute"] = True
    for name, value in (("start", args.video_start), ("end", args.video_end)):
        if value is not None:
            if not 0 <= value <= 2_147_483_647:
                raise ValueError(f"Video {name} must be a nonnegative whole second.")
            properties[name] = value
    if "end" in properties and properties["end"] <= properties.get("start", 0):
        raise ValueError("The video end must be later than its start.")
    return properties


def build_media_batch(args: argparse.Namespace) -> dict:
    media = args.image_url is not None or args.drive_video_id is not None
    link = args.html_url is not None
    if not media and not link:
        raise ValueError("Supply --html-url, --image-url, or --drive-video-id.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_:-]{0,49}", args.slide_id):
        raise ValueError("Use a valid Google Slides slide object ID.")
    if args.create_slide and not OBJECT_ID.fullmatch(args.slide_id):
        raise ValueError("A new slide object ID must have at least 5 characters.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_:-]{2,37}", args.id_prefix):
        raise ValueError("Use a 3 to 38 character object ID prefix.")
    page_size = tuple(args.page_size)
    if not all(math.isfinite(value) and value > 0 for value in page_size):
        raise ValueError("The slide page requires finite positive dimensions.")
    if args.revision is not None and not args.revision.strip():
        raise ValueError("Supply a nonblank revision ID.")
    if media != (args.frame is not None):
        raise ValueError("Use --frame exactly when adding media.")
    if link != (args.link_frame is not None) or (args.link_text is not None and not link):
        raise ValueError("Use --link-frame with --html-url. --link-text also requires --html-url.")
    playback = video_properties(args)
    if args.drive_video_id is None and (args.video_size is not None or playback):
        raise ValueError("Video dimensions and playback settings require --drive-video-id.")
    alt_text = {name: value.strip() for name, value in (
        ("title", args.media_title or ""), ("description", args.media_description or ""),
    ) if value.strip()}
    if media != bool(alt_text):
        raise ValueError("Supply meaningful alternative text when and only when adding media.")

    requests = []
    if args.create_slide:
        requests.append({"createSlide": {
            "objectId": args.slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"},
        }})
    if media:
        frame = tuple(args.frame)
        validate_frame(frame, page_size, "Media frame")
        if args.drive_video_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", args.drive_video_id):
                raise ValueError("Supply the Drive video file ID rather than its URL.")
            if args.video_size is None or not all(1 <= value <= 2_147_483_647 for value in args.video_size):
                raise ValueError("Supply positive video pixel dimensions with --video-size.")
            frame = video_frame(frame, tuple(args.video_size))
            media_id = f"{args.id_prefix}-video"
            requests.append({"createVideo": {
                "objectId": media_id, "elementProperties": element_properties(args.slide_id, frame),
                "source": "DRIVE", "id": args.drive_video_id,
            }})
            if playback:
                requests.append({"updateVideoProperties": {
                    "objectId": media_id, "videoProperties": playback, "fields": ",".join(playback),
                }})
        else:
            validate_url(args.image_url, "The image URL")
            if len(args.image_url.encode("utf-8")) > 2_000:
                raise ValueError("The image URL exceeds 2 KB.")
            media_id = f"{args.id_prefix}-image"
            requests.append({"createImage": {
                "objectId": media_id, "elementProperties": element_properties(args.slide_id, frame),
                "url": args.image_url,
            }})
        if media_id == args.slide_id:
            raise ValueError("The generated media object ID collides with the slide ID.")
        requests.append({"updatePageElementAltText": {"objectId": media_id, **alt_text}})
    if link:
        validate_url(args.html_url, "The HTML URL")
        link_frame = tuple(args.link_frame)
        validate_frame(link_frame, page_size, "Link frame")
        if media and overlaps(frame, link_frame):
            raise ValueError("The link box overlaps the media. Use a separate link frame.")
        label = (args.link_text if args.link_text is not None else "Open interactive original").strip()
        if not label or len(label.splitlines()) != 1 or any(ord(char) < 32 or ord(char) == 127 for char in label):
            raise ValueError("Supply a nonblank one-line link label.")
        link_id = f"{args.id_prefix}-link"
        if link_id == args.slide_id:
            raise ValueError("The generated link object ID collides with the slide ID.")
        requests.extend(link_requests(args.slide_id, link_id, link_frame, label, args.html_url))
    batch = {"requests": requests}
    if args.revision is not None:
        batch["writeControl"] = {"requiredRevisionId": args.revision}
    return batch


def main() -> int:
    args = parse_args()
    try:
        batch = build_media_batch(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(batch, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8",
        )
    except (ValueError, OSError) as error:
        print(f"Media slide preparation failed. {error}", file=sys.stderr)
        return 1
    print(f"Prepared {len(batch['requests'])} Slides requests in {args.output}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
