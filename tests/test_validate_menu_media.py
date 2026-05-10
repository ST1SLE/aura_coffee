"""Tests for the menu media browser-readiness validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "production" / "validate-menu-media.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_menu_media", VALIDATOR_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_atom(handle, atom_type: bytes, payload_size: int = 0) -> None:
    handle.write((payload_size + 8).to_bytes(4, "big"))
    handle.write(atom_type)
    handle.write(b"\0" * payload_size)


def _write_video(path: Path, *, faststart: bool) -> None:
    path.parent.mkdir(parents=True)
    with path.open("wb") as handle:
        _write_atom(handle, b"ftyp", 4)
        if faststart:
            _write_atom(handle, b"moov", 4)
            _write_atom(handle, b"mdat", 4)
        else:
            _write_atom(handle, b"mdat", 4)
            _write_atom(handle, b"moov", 4)


def test_menu_media_validator_accepts_faststart_video(tmp_path: Path) -> None:
    validator = _load_validator()
    media_root = tmp_path / "media" / "menu"
    _write_video(media_root / "latte" / "hero.mp4", faststart=True)
    (media_root / "latte" / "poster.webp").write_bytes(b"webp")

    errors, counts = validator._validate_media(media_root)

    assert errors == []
    assert counts == {"videos": 1, "posters": 1}


def test_menu_media_validator_rejects_late_moov_and_missing_poster(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    media_root = tmp_path / "media" / "menu"
    _write_video(media_root / "latte" / "hero.mp4", faststart=False)

    errors, counts = validator._validate_media(media_root)

    assert counts == {"videos": 1, "posters": 0}
    assert any("missing poster" in error for error in errors)
    assert any("moov atom is after mdat" in error for error in errors)
