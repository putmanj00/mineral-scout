"""USGS USMIN mine-related features (abandoned mines, tailings) via ArcGIS Online.

Verified 2026-07-12: USGS_Topographic_Mine_Symbols FeatureServer.
- Layer 8 = 1:24k POINTS (shafts, adits, prospect pits...).
- Layer 2 = 1:24k POLYGONS — this is where tailings/dumps/disturbed areas
  actually live (AZ: 262 tailings polygons vs 3 tailings points). Polygons
  are returned as centroid points so the frontend can cluster them.
f=geojson works; where= accepts SQL; maxRecordCount 2000 with
exceededTransferLimit flag when truncated.
"""
import asyncio

from ..upstream import fetch_json

BASE = ("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/"
        "USGS_Topographic_Mine_Symbols/FeatureServer")
POINTS_URL = f"{BASE}/8/query"
POLYGONS_URL = f"{BASE}/2/query"

# Waste/tailings feature types (verified against both layers' distinct values).
TAILINGS_EXACT = [
    "Mine Dump", "Slag Pile", "Ore Stockpile/Storage", "Settling Pond",
    "Leach Pond", "Evaporation Pond", "Disturbed Surface", "Disturbed Surface - Pit",
]
TAILINGS_WHERE = ("(Ftr_Type LIKE 'Tailings%' OR Ftr_Type IN ("
                  + ",".join("'" + t.replace("'", "''") + "'" for t in TAILINGS_EXACT) + "))")


def _params(bbox: tuple[float, float, float, float], where: str) -> dict:
    return {
        "where": where,
        "geometry": ",".join(str(round(v, 5)) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Ftr_Type,Ftr_Name,State,County,Topo_Name,Topo_Date,Remarks",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": "2000",
    }


def _props(p: dict, area_feature: bool) -> dict:
    return {
        "name": p.get("Ftr_Name") or p.get("Ftr_Type") or "Mine feature",
        "ftr_type": p.get("Ftr_Type"),
        "state": p.get("State"),
        "county": p.get("County"),
        "topo_name": p.get("Topo_Name"),
        "topo_date": p.get("Topo_Date"),
        "remarks": p.get("Remarks"),
        "area_feature": area_feature,  # true = centroid of a mapped polygon
        "source": "USGS USMIN",
    }


def _polygon_centroid(geom: dict) -> tuple[float, float] | None:
    """Mean of the exterior ring — fine for marker placement, not surveying."""
    try:
        ring = geom["coordinates"][0]
        if geom.get("type") == "MultiPolygon":
            ring = geom["coordinates"][0][0]
        xs = [pt[0] for pt in ring]
        ys = [pt[1] for pt in ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    except (KeyError, IndexError, TypeError, ZeroDivisionError):
        return None


async def query_bbox(bbox: tuple[float, float, float, float], tailings_only: bool) -> dict:
    """Points layer always; polygon layer only when hunting tailings/dumps
    (polygon queries are heavier and points cover the classic mine features)."""
    where = TAILINGS_WHERE if tailings_only else "1=1"
    tasks = [fetch_json("usmin", POINTS_URL, params=_params(bbox, where))]
    if tailings_only:
        tasks.append(fetch_json("usmin", POLYGONS_URL, params=_params(bbox, TAILINGS_WHERE)))
    results = await asyncio.gather(*tasks)

    features, truncated = [], False
    for data in results:
        truncated = truncated or bool(data.get("exceededTransferLimit")
                                      or data.get("properties", {}).get("exceededTransferLimit"))
        for f in data.get("features", []):
            geom = f.get("geometry") or {}
            p = f.get("properties") or {}
            if geom.get("type") == "Point":
                features.append({"type": "Feature", "geometry": geom,
                                 "properties": _props(p, False)})
            elif geom.get("type") in ("Polygon", "MultiPolygon"):
                centroid = _polygon_centroid(geom)
                if centroid:
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": list(centroid)},
                        "properties": _props(p, True),
                    })
        truncated = truncated or len(data.get("features", [])) >= 2000
    return {"type": "FeatureCollection", "features": features, "truncated": truncated}
