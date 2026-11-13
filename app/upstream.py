"""Shared upstream HTTP fetch with TTL cache.

All source modules go through fetch_json() so caching, timeouts, and error
shape stay consistent. Upstream failures raise UpstreamError; API routes map
that to a 502 with the source name so the UI can show which layer is down.
"""
import json
from urllib.parse import urlencode

import httpx

from . import cache
from .config import settings


class UpstreamError(Exception):
    def __init__(self, source: str, detail: str):
        self.source = source
        self.detail = detail
        super().__init__(f"{source}: {detail}")


async def _request(source: str, url: str, *, params: dict | None, headers: dict | None,
                   method: str = "GET", json_body: dict | None = None,
                   timeout: float | None = None) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout or settings.upstream_timeout,
                                     follow_redirects=True) as client:
            resp = await client.request(method, url, params=params, headers=headers, json=json_body)
    except httpx.HTTPError as exc:
        raise UpstreamError(source, f"request failed: {exc!r}") from exc
    if resp.status_code != 200:
        raise UpstreamError(source, f"HTTP {resp.status_code}")
    return resp


def _cache_key(source: str, url: str, params: dict | None, json_body: dict | None = None) -> str:
    body = json.dumps(json_body, sort_keys=True) if json_body else ""
    return f"{source}|{url}|{urlencode(sorted((params or {}).items()))}|{body}"


async def fetch_json(source: str, url: str, params: dict | None = None,
                     headers: dict | None = None, ttl: int | None = None,
                     method: str = "GET", json_body: dict | None = None,
                     timeout: float | None = None):
    key = _cache_key(source, url, params, json_body)
    cached = cache.get(key)
    if cached is not None:
        return cached
    resp = await _request(source, url, params=params, headers=headers,
                          method=method, json_body=json_body, timeout=timeout)
    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise UpstreamError(source, f"non-JSON response: {resp.text[:200]}") from exc
    # ArcGIS servers return HTTP 200 with an embedded error object.
    if isinstance(data, dict) and "error" in data and "features" not in data:
        raise UpstreamError(source, f"upstream error: {json.dumps(data['error'])[:300]}")
    cache.put(key, data, ttl=ttl)
    return data


async def fetch_text(source: str, url: str, params: dict | None = None,
                     headers: dict | None = None, ttl: int | None = None,
                     timeout: float | None = None, validate=None) -> str:
    """validate(text) -> error detail str or None. Invalid bodies raise and are
    NOT cached — some upstreams (MRDS WFS) return errors with HTTP 200, and a
    cached error would keep failing for the whole TTL after upstream recovers."""
    key = _cache_key(source, url, params)
    cached = cache.get(key)
    if cached is not None:
        return cached
    resp = await _request(source, url, params=params, headers=headers, timeout=timeout)
    text = resp.text
    if validate is not None:
        detail = validate(text)
        if detail:
            raise UpstreamError(source, detail)
    cache.put(key, text, ttl=ttl)
    return text
