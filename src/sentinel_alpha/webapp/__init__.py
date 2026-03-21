from __future__ import annotations

from pathlib import Path


def static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"
