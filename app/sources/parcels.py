"""Parcel owner lookup: county-registry approach (verified 2026-07-12).

Tier 1: counties with free open ArcGIS REST returning owner names —
query live, return assessor-record owner (may be an LLC/trust, may lag sales).
Tier 2: counties with a known viewer/search page — link out.
Tier 3: NETR Online public-records directory for any US county.

Honest ceiling (research-verified): NJ redacts owners statewide (Daniel's
Law); CA counties mostly publish no owner names online; KY owner data sits
behind county PVA subscriptions. The API says so instead of pretending.
"""
from urllib.parse import quote

from ..upstream import UpstreamError, fetch_json

OWNER_CAVEAT = (
    "Assessor-record owner: may be a trust/LLC, and can lag recent sales by "
    "weeks. Confirm via the county assessor link before making contact."
)

# Counties with verified open REST services that return owner names.
COUNTY_REST = {
    ("AZ", "Maricopa"): {
        "url": "https://gis.maricopa.gov/arcgis/rest/services/IndividualService/Parcel/MapServer/1/query",
        "fields": "APN,OwnerName,PropertyFullStreetAddress,AssessorWebLink",
        "owner_keys": ["OwnerName"],
        "apn_key": "APN",
        "link": lambda a: a.get("AssessorWebLink") or f"https://mcassessor.maricopa.gov/mcs/?q={quote(str(a.get('APN', '')))}",
    },
    ("AZ", "Yavapai"): {
        "url": "https://gis.yavapaiaz.gov/arcgis/rest/services/ServicesMiscellaneous/ParcelsPlus/FeatureServer/0/query",
        "fields": "PARLABEL,NAME,ADDRESS,CITY",
        "owner_keys": ["NAME"],
        "apn_key": "PARLABEL",
        "link": lambda a: f"https://gis.yavapaiaz.gov/V4/map.aspx?search={quote(str(a.get('PARLABEL', '')))}",
    },
    ("AZ", "Cochise"): {
        "url": "https://services6.arcgis.com/Yxem0VOcqSy8T6TE/arcgis/rest/services/Cad_Parcel_TaxInfo/FeatureServer/0/query",
        "fields": "apn,owner_name1,owner_name2,situs_address,city,state",
        "owner_keys": ["owner_name1", "owner_name2"],
        "apn_key": "apn",
        "link": lambda a: "https://asr.cochise.gov/",
    },
}

# Known assessor search pages (no deep-link param) for other AZ rockhounding counties.
COUNTY_LINKS = {
    ("AZ", "Mohave"): "https://www.mohave.gov/departments/assessor/assessor-search/",
    ("AZ", "La Paz"): "http://publicrecords.lapazassessor.com/assessor/web/",
    ("AZ", "Pinal"): "https://app1.pinal.gov/search/parcel-search.aspx",
}

STATE_CEILINGS = {
    "NJ": "New Jersey removes owner names from all public parcel services (Daniel's Law) — contact the tax assessor's office directly.",
    "CA": "Most California county assessors do not publish owner names online — expect an in-person or written records request.",
    "KY": "Kentucky statewide GIS is geometry-only; owner data sits with county PVAs, often behind a paid subscription.",
}


def _netr_url(state_code: str, county: str) -> str:
    slug = county.lower().replace(" county", "").strip().replace(" ", "_")
    return f"https://publicrecords.netronline.com/state/{quote(state_code)}/county/{quote(slug)}"


async def owner_lookup(lat: float, lon: float, state_code: str | None, county: str | None) -> dict:
    """Returns {owner, apn, links: [{label,url}], notes: [str]}."""
    links: list[dict] = []
    notes: list[str] = []
    owner = None
    apn = None

    county_clean = (county or "").replace(" County", "").strip()
    reg = COUNTY_REST.get((state_code, county_clean)) if state_code else None
    if reg:
        try:
            data = await fetch_json("parcels", reg["url"], params={
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": reg["fields"],
                "returnGeometry": "false",
                "f": "json",
            })
            feats = data.get("features") or []
            if feats:
                attrs = feats[0].get("attributes") or {}
                owner = ", ".join(str(attrs[k]).strip() for k in reg["owner_keys"]
                                  if attrs.get(k) and str(attrs[k]).strip())or None
                apn = attrs.get(reg["apn_key"])
                links.append({"label": f"{county_clean} County assessor record", "url": reg["link"](attrs)})
                if owner:
                    notes.append(OWNER_CAVEAT)
        except UpstreamError as exc:
            notes.append(f"County parcel service unavailable ({exc.detail}) — use the assessor links below.")

    if not owner and state_code and (state_code, county_clean) in COUNTY_LINKS:
        links.append({"label": f"{county_clean} County assessor search",
                      "url": COUNTY_LINKS[(state_code, county_clean)]})

    if state_code and county_clean:
        links.append({"label": f"All {county_clean} County public-records offices (NETR)",
                      "url": _netr_url(state_code, county_clean)})
    if state_code in STATE_CEILINGS:
        notes.append(STATE_CEILINGS[state_code])
    if not owner:
        notes.append("Owner name not available from a free online service here — "
                     "the assessor/recorder links can identify the owner.")
    return {"owner": owner, "apn": apn, "links": links, "notes": notes}
