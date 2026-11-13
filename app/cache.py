"""File-backed TTL cache for upstream API responses.

Keyed by sha256 of (source, url, params). Values are JSON documents.
Keeps repeat map pans cheap and shields the app from flaky/slow USGS+BLM servers.
"""
import hashlib
import json
import time
from typing import Any

from .config import settings


def _path_for(key: str):
    digest = hashlib.sha256(key.encode()).hexdigest()
    return settings.cache_dir / digest[:2] / f"{digest}.json"


def get(key: str) -> Any | None:
    path = _path_for(key)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    if doc.get("expires", 0) < time.time():
        try:
            path.unlink()
        except OSError:
            pass
        return None
    return doc.get("value")


def put(key: str, value: Any, ttl: int | None = None) -> None:
    path = _path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"expires": time.time() + (ttl if ttl is not None else settings.cache_ttl), "value": value}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    tmp.replace(path)
