"""Reverse geocode lat/lon -> US state + county via Census geocoder (free, no key)."""
from ..upstream import UpstreamError, fetch_json

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"


async def state_county(lat: float, lon: float) -> dict | None:
    params = {
        "x": str(lon),
        "y": str(lat),
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "Counties,States",
        "format": "json",
    }
    try:
        data = await fetch_json("census", CENSUS_URL, params=params)
    except UpstreamError:
        return None  # geocode is enrichment, not core — degrade quietly
    geos = (data.get("result") or {}).get("geographies") or {}
    states = geos.get("States") or []
    counties = geos.get("Counties") or []
    if not states:
        return None
    return {
        "state_code": states[0].get("STUSAB"),
        "state_name": states[0].get("NAME"),
        "county": counties[0].get("NAME") if counties else None,
    }
