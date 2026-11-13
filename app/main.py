"""Mineral Scout — find minerals, check land status, contact owners.

Data sources (all verified live 2026-07-12): USGS MRDS, USGS USMIN,
BLM SMA + MLRS claims, USGS PAD-US 4.1, Census geocoder, county assessor
parcel services, mindat.org (optional API key).
"""
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import land_status, laws, varieties
from .config import settings
from .sources import blm, mindat, mrds, usmin
from .upstream import UpstreamError, fetch_json

app = FastAPI(title="Mineral Scout", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

MAX_BBOX_DEG2 = 64.0  # backstop; the frontend clamps its own requests to ~6x6 deg

SMA_LEGEND = [
    {"label": "BLM", "color": "#ffe596"},
    {"label": "Forest Service", "color": "#93cc96"},
    {"label": "NPS", "color": "#c4a6d9"},
    {"label": "Fish & Wildlife", "color": "#ffa77f"},
    {"label": "State", "color": "#92c5eb"},
    {"label": "Tribal", "color": "#d2b48c"},
    {"label": "Military/other fed", "color": "#fbb1b1"},
    {"label": "Private (white)", "color": "#ffffff"},
]


def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    try:
        w, s, e, n = (float(v) for v in raw.split(","))
    except (TypeError, ValueError):
        raise HTTPException(400, "bbox must be 'west,south,east,north' in decimal degrees")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise HTTPException(400, "bbox out of range or misordered (need west<east, south<north)")
    if (e - w) * (n - s) > MAX_BBOX_DEG2:
        raise HTTPException(400, "bbox too large — zoom in (max ~8x8 degrees)")
    return (w, s, e, n)


def upstream_502(exc: UpstreamError) -> HTTPException:
    return HTTPException(502, f"Upstream {exc.source} failed: {exc.detail}")


@app.get("/api/health")
async def health():
    return {"ok": True, "version": app.version}


def resolve_commodity_terms(raw: str) -> tuple[list[str], list[dict], list[str]]:
    """User search terms -> (mrds codes, matched variety entries, unknown terms).
    A term can be a commodity name (Gold), a raw code (REE), or a named
    variety (Kentucky agate) which expands to its base codes."""
    codes: list[str] = []
    variety_hits: list[dict] = []
    unknown: list[str] = []
    for term in filter(None, (t.strip() for t in raw.split(","))):
        variety = varieties.resolve(term)
        if variety:
            variety_hits.append(variety)
            codes.extend(variety["codes"])
            continue
        code = mrds.resolve_commodity(term)
        if code:
            codes.append(code)
        else:
            unknown.append(term)
    return list(dict.fromkeys(codes)), variety_hits, unknown


@app.get("/api/config")
async def config():
    return {
        "commodities": sorted(c.title() for c in mrds.COMMODITY_CODES),
        "varieties": varieties.public_list(),
        "statuses": mrds.DEV_STATUSES,
        "mindat_enabled": mindat.enabled(),
        "min_zoom_sites": 6,
        "ownership": {
            "tiles": blm.SMA_TILE_URL,
            "attribution": "BLM Surface Management Agency",
            "legend": SMA_LEGEND,
        },
    }


@app.get("/api/sites")
async def sites(bbox: str, commodities: str = "", statuses: str = ""):
    box = parse_bbox(bbox)
    codes, variety_hits, unknown = resolve_commodity_terms(commodities)
    status_list = [s for s in (x.strip() for x in statuses.split(",")) if s]
    try:
        raw, truncated = await mrds.query_bbox(box)
    except UpstreamError as exc:
        raise upstream_502(exc)
    filtered = mrds.filter_sites(raw, codes, status_list)
    gj = mrds.to_geojson(filtered, truncated)
    warnings = []
    if unknown:
        warnings.append(f"Unrecognized commodity ignored: {', '.join(unknown)}")
    for v in variety_hits:
        warnings.append(f"“{v['name']}” searched as {', '.join(v['codes'])} — "
                        "famous variety ground often has no MRDS record; use its region card.")
    if warnings:
        gj["warnings"] = warnings
    return gj


_AUDIT_KEYS = {"inserted_by", "insert_date", "updated_by", "update_date", "line"}


def _clean(obj):
    """Strip MRDS audit-trail fields so the detail payload is UI-sized."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k not in _AUDIT_KEYS}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def _aslist(section) -> list:
    """MRDS record sections are a dict for one entry, a list for several."""
    if section is None:
        return []
    if isinstance(section, list):
        return section
    return [section]


@app.get("/api/sites/{dep_id}")
async def site_detail(dep_id: str):
    """What's at this location: full commodity list (primary/secondary),
    ore/gangue materials, rocks, deposit info — from the rich MRDS record."""
    if not dep_id.isdigit():
        raise HTTPException(400, "dep_id must be numeric")
    try:
        rec = await fetch_json("mrds", mrds.RECORD_URL.format(dep_id=dep_id), ttl=30 * 86400)
    except UpstreamError as exc:
        raise upstream_502(exc)
    p = rec.get("properties") or {}
    deposits = p.get("deposits") or {}
    location = _aslist(p.get("location"))
    return {
        "id": dep_id,
        "url": f"https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id={dep_id}",
        "coordinates": (rec.get("geometry") or {}).get("coordinates"),
        "names": _clean(_aslist(p.get("name"))),
        "commodities": _clean(_aslist(p.get("commodity"))),
        "materials": _clean(_aslist(p.get("material"))),
        "rocks": _clean(_aslist(p.get("rock"))),
        "deposit": {k: deposits.get(k) for k in
                    ("dev_st", "dep_tp", "oper_tp", "prod_size", "deposit_size")},
        "location": _clean(location[0]) if location else {},
        "comment": _clean(_aslist(p.get("comment"))[:3]),
    }


@app.get("/api/mines")
async def mines(bbox: str, tailings_only: str = ""):
    box = parse_bbox(bbox)
    try:
        return await usmin.query_bbox(box, tailings_only == "1")
    except UpstreamError as exc:
        raise upstream_502(exc)


@app.get("/api/claims")
async def claims(bbox: str):
    box = parse_bbox(bbox)
    try:
        return await blm.claims_bbox(box)
    except UpstreamError as exc:
        raise upstream_502(exc)


@app.get("/api/land-status")
async def land_status_ep(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    return await land_status.check(lat, lon)


@app.get("/api/laws")
async def laws_index():
    return {"states": laws.list_states()}


@app.get("/api/laws/{code}")
async def laws_state(code: str):
    state = laws.get_state(code)
    if not state:
        raise HTTPException(404, f"No law summary for '{code}' yet — federal rules still apply; "
                                 "check the state geological survey.")
    return state


@app.get("/api/mindat/localities")
async def mindat_localities(bbox: str):
    if not mindat.enabled():
        raise HTTPException(503, "Mindat layer disabled: set MSCOUT_MINDAT_API_KEY "
                                 "(free key with a mindat.org account).")
    box = parse_bbox(bbox)
    try:
        return await mindat.localities_bbox(box)
    except UpstreamError as exc:
        raise upstream_502(exc)


@app.get("/api/export.gpx")
async def export_gpx(bbox: str, commodities: str = "", statuses: str = "", include_mines: str = ""):
    box = parse_bbox(bbox)
    codes, _varieties, _unknown = resolve_commodity_terms(commodities)
    status_list = [s for s in (x.strip() for x in statuses.split(",")) if s]
    try:
        raw, _truncated = await mrds.query_bbox(box)
    except UpstreamError as exc:
        raise upstream_502(exc)
    sites_list = mrds.filter_sites(raw, codes, status_list)
    wpts = []
    for s in sites_list:
        name = escape(s.get("site_name") or "Unnamed")
        desc = escape(f"{s.get('dev_stat', 'Unknown')} — {(s.get('code_list') or '').strip()} (USGS MRDS)")
        wpts.append(f'<wpt lat="{s["lat"]}" lon="{s["lon"]}"><name>{name}</name><desc>{desc}</desc></wpt>')
    if include_mines == "1":
        try:
            mine_gj = await usmin.query_bbox(box, False)
            for f in mine_gj["features"]:
                lon_, lat_ = f["geometry"]["coordinates"]
                p = f["properties"]
                name = escape(p.get("name") or "Mine feature")
                desc = escape(f"{p.get('ftr_type', '?')} (USGS USMIN) — DO NOT ENTER")
                wpts.append(f'<wpt lat="{lat_}" lon="{lon_}"><name>{name}</name><desc>{desc}</desc></wpt>')
        except UpstreamError:
            pass  # GPX still useful with sites only
    gpx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<gpx version="1.1" creator="Mineral Scout" '
           'xmlns="http://www.topografix.com/GPX/1/1">\n' + "\n".join(wpts) + "\n</gpx>")
    return Response(gpx, media_type="application/gpx+xml",
                    headers={"Content-Disposition": 'attachment; filename="mineral-scout.gpx"'})


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
