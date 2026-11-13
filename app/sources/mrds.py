"""USGS MRDS (Mineral Resources Data System) via mrdata.usgs.gov WFS.

Verified 2026-07-12:
- WFS returns GML only (application/json rejected). bbox= param takes
  lon,lat axis order despite WFS 1.1.0. maxFeatures/startIndex work.
- Combining BBOX + PropertyIsLike in one OGC Filter is broken server-side
  (msPostGISLayerWhichShapes error), so we query by bbox and filter
  commodities/status here in the backend.
- code_list is space-separated commodity codes with a leading space (' CU AU').
- Per-record rich JSON: https://mrdata.usgs.gov/mrds/json/{dep_id}
"""
import xml.etree.ElementTree as ET

from ..upstream import UpstreamError, fetch_text

WFS_URL = "https://mrdata.usgs.gov/wfs/mrds"
RECORD_URL = "https://mrdata.usgs.gov/mrds/json/{dep_id}"
MAX_FEATURES = 2000

# Common commodity name -> MRDS code. Metals use chemical-symbol codes
# (verified 'CU AU' in live code_list). Unknown names fall through: any
# 1-4 char alpha token the user types is treated as a raw code.
COMMODITY_CODES = {
    "gold": "AU", "silver": "AG", "copper": "CU", "lead": "PB", "zinc": "ZN",
    "iron": "FE", "manganese": "MN", "molybdenum": "MO", "tin": "SN",
    "tungsten": "W", "uranium": "U", "vanadium": "V", "nickel": "NI",
    "cobalt": "CO", "chromium": "CR", "titanium": "TI", "antimony": "SB",
    "mercury": "HG", "beryllium": "BE", "lithium": "LI", "platinum": "PT",
    "palladium": "PD", "aluminum": "AL", "magnesium": "MG", "barium": "BA",
    "barite": "BA", "fluorite": "F", "fluorine": "F", "sulfur": "S",
    "boron": "B", "bismuth": "BI", "arsenic": "AS", "cadmium": "CD",
    "thorium": "TH", "niobium": "NB", "tantalum": "TA", "zirconium": "ZR",
    "selenium": "SE", "tellurium": "TE", "rhenium": "RE", "potash": "K",
    "phosphorus": "P", "strontium": "SR", "cesium": "CS", "rubidium": "RB",
    "gallium": "GA", "germanium": "GE", "indium": "IN", "scandium": "SC",
    "yttrium": "Y", "cerium": "CE", "lanthanum": "LA",
}

DEV_STATUSES = ["Producer", "Past Producer", "Prospect", "Occurrence", "Plant", "Unknown"]

# code -> display name (reverse of COMMODITY_CODES plus non-metal codes
# observed live in code_list: GEM, SIL, STN_C, CLY, SDG ...)
CODE_NAMES: dict[str, str] = {code: name.title() for name, code in COMMODITY_CODES.items()}
CODE_NAMES.update({
    "BA": "Barite", "F": "Fluorite",  # prefer the mineral over the element
    "GEM": "Gemstone", "SIL": "Silica", "STN_C": "Stone (crushed)",
    "STN_D": "Stone (dimension)", "CLY": "Clay", "SDG": "Sand & Gravel",
    "REE": "Rare earths", "PGE": "Platinum group", "COG": "Coal",
})


def codes_to_names(code_list: str) -> str:
    codes = (code_list or "").split()
    return ", ".join(CODE_NAMES.get(c, c) for c in codes)


def resolve_commodity(name: str) -> str | None:
    name = name.strip().lower()
    if not name:
        return None
    if name in COMMODITY_CODES:
        return COMMODITY_CODES[name]
    raw = name.upper()
    if raw.isalpha() and 1 <= len(raw) <= 4:
        return raw
    return None


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_gml(xml_text: str) -> tuple[list[dict], int]:
    """Parse a WFS GML FeatureCollection -> (site dicts, raw featureMember count).

    The raw count matters for truncation detection: members without a usable
    gml:pos are dropped from the site list but still counted against the
    server's maxFeatures cap."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise UpstreamError("mrds", f"bad GML: {exc}") from exc
    sites = []
    members = 0
    for member in root.iter():
        if _localname(member.tag) != "featureMember":
            continue
        members += 1
        site: dict = {}
        for el in member.iter():
            name = _localname(el.tag)
            text = (el.text or "").strip()
            if name == "pos" and text:
                # gml:pos is 'lat lon' (verified live)
                parts = text.split()
                if len(parts) == 2:
                    site["lat"], site["lon"] = float(parts[0]), float(parts[1])
            elif name in ("dep_id", "site_name", "dev_stat", "code_list", "url") and text:
                site[name] = text
        if "lat" in site and "lon" in site:
            sites.append(site)
    return sites, members


def _wfs_validate(xml_text: str) -> str | None:
    if "ExceptionReport" in xml_text or "ServiceException" in xml_text:
        return f"WFS exception: {xml_text[:300]}"
    return None


async def query_bbox(bbox: tuple[float, float, float, float]) -> tuple[list[dict], bool]:
    """Returns (sites, truncated)."""
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": "mrds",
        "bbox": ",".join(str(round(v, 5)) for v in bbox),  # lon,lat order (verified)
        "maxFeatures": str(MAX_FEATURES),
    }
    xml_text = await fetch_text("mrds", WFS_URL, params=params, validate=_wfs_validate)
    sites, members = parse_gml(xml_text)
    return sites, members >= MAX_FEATURES


def filter_sites(sites: list[dict], commodity_codes: list[str], statuses: list[str]) -> list[dict]:
    out = []
    wanted = {c.upper() for c in commodity_codes}
    wanted_status = set(statuses)
    for s in sites:
        codes = set((s.get("code_list") or "").split())
        status = s.get("dev_stat") or "Unknown"
        if wanted and not (codes & wanted):
            continue
        if wanted_status and status not in wanted_status:
            continue
        out.append(s)
    return out


def to_geojson(sites: list[dict], truncated: bool) -> dict:
    features = []
    for s in sites:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": {
                "id": s.get("dep_id"),
                "name": s.get("site_name") or "Unnamed",
                "dev_status": s.get("dev_stat") or "Unknown",
                "commodities": (s.get("code_list") or "").strip(),
                "commodity_names": codes_to_names(s.get("code_list") or ""),
                "url": s.get("url") or (
                    f"https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id={s['dep_id']}"
                    if s.get("dep_id") else None),
                "source": "USGS MRDS",
            },
        })
    return {"type": "FeatureCollection", "features": features, "truncated": truncated}
