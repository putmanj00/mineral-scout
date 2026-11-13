"""mindat.org API (api.mindat.org/v1). Verified 2026-07-12.

Auth: 'Authorization: Token <key>' header; free key with a mindat.org account.
Localities require auth; bbox search = POST /v1/geoloc-poly/ with a GeoJSON-ish
polygon body. Without a key the API endpoints here return 503 so the UI can
explain how to enable the layer.
"""
from ..config import settings
from ..upstream import fetch_json

BASE = "https://api.mindat.org/v1"


def enabled() -> bool:
    return bool(settings.mindat_api_key)


def _headers() -> dict:
    return {"Authorization": f"Token {settings.mindat_api_key}"}


async def localities_bbox(bbox: tuple[float, float, float, float]) -> dict:
    """bbox -> GeoJSON FeatureCollection of mindat localities."""
    w, s, e, n = bbox
    body = {"polygon": {"type": "Polygon",
                        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}}
    data = await fetch_json("mindat", f"{BASE}/geoloc-poly/", method="POST",
                            json_body=body, headers=_headers(), ttl=7 * 86400)
    results = data.get("results") if isinstance(data, dict) else data
    features = []
    for loc in results or []:
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": loc.get("id"),
                "name": loc.get("txt") or "Locality",
                "minerals": ", ".join((loc.get("elements") or "").strip("-").split("-"))
                            if isinstance(loc.get("elements"), str) else None,
                "source": "mindat.org",
            },
        })
    return {"type": "FeatureCollection", "features": features, "truncated": False}
