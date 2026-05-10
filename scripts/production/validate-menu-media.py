#!/usr/bin/env python3
"""Validate customer menu media files for browser playback readiness."""

# START_MODULE_CONTRACT
#   PURPOSE: Validate public customer menu media assets before staging or
#            production deploy so browser video playback does not stall on
#            delayed MP4 metadata.
#   SCOPE:   Filesystem validation only: menu video directories, required
#            posters, MP4 top-level atom layout, and optional size limits.
#   DEPENDS: Python stdlib (argparse, pathlib, sys).
#   LINKS:   docs/shipping-website/README.md Stage 3,
#            docs/design/video-media-grace-plan.md.
#   ROLE:    TOOLING
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   main - CLI entry point for menu media asset validation
# END_MODULE_MAP

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BOX_HEADER_BYTES = 8


def _top_level_atom_offsets(path: Path) -> tuple[dict[str, int], list[str]]:
    offsets: dict[str, int] = {}
    errors: list[str] = []
    file_size = path.stat().st_size
    offset = 0

    with path.open("rb") as handle:
        while offset + _BOX_HEADER_BYTES <= file_size:
            handle.seek(offset)
            header = handle.read(_BOX_HEADER_BYTES)
            if len(header) != _BOX_HEADER_BYTES:
                errors.append(f"{path}: truncated MP4 atom header at byte {offset}")
                break

            atom_size = int.from_bytes(header[:4], "big")
            atom_type = header[4:8]
            header_size = _BOX_HEADER_BYTES

            if atom_size == 1:
                large_size = handle.read(8)
                if len(large_size) != 8:
                    errors.append(f"{path}: truncated MP4 large-size atom at byte {offset}")
                    break
                atom_size = int.from_bytes(large_size, "big")
                header_size = 16
            elif atom_size == 0:
                atom_size = file_size - offset

            if atom_size < header_size:
                errors.append(f"{path}: invalid MP4 atom size at byte {offset}")
                break

            try:
                atom_name = atom_type.decode("ascii")
            except UnicodeDecodeError:
                atom_name = ""
            if atom_name in {"moov", "mdat"} and atom_name not in offsets:
                offsets[atom_name] = offset

            next_offset = offset + atom_size
            if next_offset <= offset:
                errors.append(f"{path}: invalid MP4 atom progression at byte {offset}")
                break
            offset = next_offset

    return offsets, errors


def _validate_media(
    media_root: Path,
    *,
    max_video_bytes: int | None = None,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    counts = {"videos": 0, "posters": 0}

    if not media_root.is_dir():
        return [f"{media_root}: media root is missing or not a directory"], counts

    for video_path in sorted(media_root.glob("*/hero.mp4")):
        counts["videos"] += 1
        poster_path = video_path.with_name("poster.webp")
        if poster_path.is_file():
            counts["posters"] += 1
        else:
            errors.append(f"{poster_path}: missing poster for video media")

        if max_video_bytes is not None and video_path.stat().st_size > max_video_bytes:
            errors.append(
                f"{video_path}: video size exceeds {max_video_bytes} bytes"
            )

        offsets, atom_errors = _top_level_atom_offsets(video_path)
        errors.extend(atom_errors)
        if "moov" not in offsets:
            errors.append(f"{video_path}: missing MP4 moov atom")
        if "mdat" not in offsets:
            errors.append(f"{video_path}: missing MP4 mdat atom")
        if (
            "moov" in offsets
            and "mdat" in offsets
            and offsets["moov"] > offsets["mdat"]
        ):
            errors.append(
                f"{video_path}: MP4 is not faststart; moov atom is after mdat"
            )

    if counts["videos"] == 0:
        errors.append(f"{media_root}: no */hero.mp4 files found")

    return errors, counts


# START_CONTRACT: main
#   PURPOSE: CLI entry point for validating menu media browser readiness.
#   INPUTS:  argv: list[str] | None — command-line args or None for sys.argv.
#   OUTPUTS: int — process exit code; 0 if valid, 1 if validation failed.
#   SIDE_EFFECTS: Reads public media files and writes sanitized validation
#                 summary/errors to stdout/stderr. No secrets or PII.
#   LINKS:   docs/shipping-website/README.md Stage 3, INV-015.
# END_CONTRACT: main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Aura Coffee public menu media files."
    )
    parser.add_argument(
        "media_root",
        nargs="?",
        type=Path,
        default=Path("web/customer/public/media/menu"),
    )
    parser.add_argument("--max-video-bytes", type=int)
    args = parser.parse_args(argv)

    errors, counts = _validate_media(
        args.media_root,
        max_video_bytes=args.max_video_bytes,
    )
    if errors:
        print("menu media validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("menu media validation passed")
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
