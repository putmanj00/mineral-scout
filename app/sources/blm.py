"""BLM services: SMA land ownership (gis.blm.gov/arcgis) and MLRS mining
claims (gis.blm.gov/nlsdb). Verified 2026-07-12.

- SMA point query: layer 1 of BLM_Natl_SMA_Cached_with_PriUnk; PVT = private.
- SMA tile overlay: .../MapServer/tile/{z}/{y}/{x} (JPEG, Web Mercator).
- Claims: MiningClaims/MapServer layer 1 (Active) / 2 (Closed, slow — 60s).
- CSE_TYPE_NR has no textual domain; map hardcoded from layer renderer.
"""
from ..upstream import fetch_json

SMA_QUERY_URL = ("https://gis.blm.gov/arcgis/rest/services/lands/"
                 "BLM_Natl_SMA_Cached_with_PriUnk/MapServer/1/query")
SMA_TILE_URL = ("https://gis.blm.gov/arcgis/rest/services/lands/"
                "BLM_Natl_SMA_Cached_with_PriUnk/MapServer/tile/{z}/{y}/{x}")
CLAIMS_ACTIVE_URL = ("https://gis.blm.gov/nlsdb/rest/services/Mining_Claims/"
                     "MiningClaims/MapServer/1/query")

CLAIM_TYPES = {
    "384101": "Lode Claim", "384103": "Lode Claim",
    "384201": "Placer Claim", "384203": "Placer Claim",
    "384301": "Tunnel Site", "384303": "Tunnel Site",
    "384401": "Mill Site", "384403": "Mill Site",
}

AGENCY_NAMES = {
    "BLM": "Bureau of Land Management",
    "USFS": "US Forest Service",
    "FS": "US Forest Service",
    "NPS": "National Park Service",
    "USFW": "US Fish & Wildlife Service",
    "FWS": "US Fish & Wildlife Service",
    "BOR": "Bureau of Reclamation",
    "BIA": "Bureau of Indian Affairs (tribal land)",
    "DOD": "Department of Defense",
    "DOE": "Department of Energy",
    "COE": "US Army Corps of Engineers",
    "ST": "State",
    "STATE": "State",
    "LG": "Local government",
    "PVT": "Private / unknown",
    "UND": "Undetermined",
    "OTFE": "Other federal",
}


async def sma_at_point(lat: float, lon: float) -> dict | None:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ADMIN_AGENCY_CODE,ADMIN_UNIT_NAME,ADMIN_DEPT_CODE,ADMIN_ST",
        "returnGeometry": "false",
        "f": "json",
    }
    data = await fetch_json("blm-sma", SMA_QUERY_URL, params=params)
    feats = data.get("features") or []
    if not feats:
        return None
    attrs = feats[0].get("attributes") or {}
    code = (attrs.get("ADMIN_AGENCY_CODE") or "").strip()
    return {
        "agency_code": code,
        "agency_name": AGENCY_NAMES.get(code.upper(), code or "Unknown"),
        "unit_name": attrs.get("ADMIN_UNIT_NAME"),
        "dept_code": attrs.get("ADMIN_DEPT_CODE"),
        "state": attrs.get("ADMIN_ST"),
    }


def _claim_props(p: dict) -> dict:
    return {
        "name": p.get("CSE_NAME") or "Mining claim",
        "serial": p.get("CSE_NR"),
        "case_type": CLAIM_TYPES.get(str(p.get("CSE_TYPE_NR") or ""), str(p.get("CSE_TYPE_NR") or "?")),
        "disposition": p.get("CSE_DISP"),
        "acres": p.get("RCRD_ACRS"),
        "source": "BLM MLRS",
    }


async def claims_bbox(bbox: tuple[float, float, float, float]) -> dict:
    params = {
        "geometry": ",".join(str(round(v, 5)) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CSE_NAME,CSE_TYPE_NR,CSE_DISP,CSE_NR,RCRD_ACRS",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": "2000",
    }
    data = await fetch_json("blm-claims", CLAIMS_ACTIVE_URL, params=params, timeout=60.0)
    features = [{
        "type": "Feature",
        "geometry": f.get("geometry"),
        "properties": _claim_props(f.get("properties") or {}),
    } for f in data.get("features", []) if f.get("geometry")]
    return {
        "type": "FeatureCollection",
        "features": features,
        "truncated": bool(data.get("exceededTransferLimit") or len(features) >= 2000),
    }


async def claims_at_point(lat: float, lon: float) -> list[dict]:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CSE_NAME,CSE_TYPE_NR,CSE_DISP,CSE_NR",
        "returnGeometry": "false",
        "f": "json",
    }
    data = await fetch_json("blm-claims", CLAIMS_ACTIVE_URL, params=params, timeout=60.0)
    return [_claim_props(f.get("attributes") or {}) for f in (data.get("features") or [])]
