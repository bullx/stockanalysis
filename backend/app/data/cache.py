"""Disk cache under output/cache/ with a time-to-live per key."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def cache_root(output_dir: str = "output") -> Path:
    path = Path(output_dir) / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(key: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)[:180]


def cache_get(namespace: str, key: str, ttl_s: int, output_dir: str = "output") -> Any | None:
    path = cache_root(output_dir) / namespace / f"{_safe_name(key)}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    saved = payload.get("saved_at", 0)
    if ttl_s > 0 and (time.time() - saved) > ttl_s:
        return None
    return payload.get("data")


def cache_set(namespace: str, key: str, data: Any, output_dir: str = "output") -> None:
    folder = cache_root(output_dir) / namespace
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe_name(key)}.json"
    path.write_text(
        json.dumps({"saved_at": time.time(), "data": data}, default=str),
        encoding="utf-8",
    )
