"""USGS PAD-US 4.1 Manager Name layer — point-in-polygon land manager lookup.

Verified 2026-07-12. Empty result = not in any protected/public tract
(usually private). Attribute values are coded; common codes mapped here,
unknown codes shown raw.
"""
from ..upstream import fetch_json

QUERY_URL = ("https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/"
             "Manager_Name_PADUS/FeatureServer/0/query")

MANAGER_NAMES = {
    "BLM": "Bureau of Land Management", "USFS": "US Forest Service",
    "NPS": "National Park Service", "FWS": "US Fish & Wildlife Service",
    "DOD": "Department of Defense", "DOE": "Department of Energy",
    "USBR": "Bureau of Reclamation", "USACE": "US Army Corps of Engineers",
    "NRCS": "Natural Resources Conservation Service", "TVA": "Tennessee Valley Authority",
    "OTHF": "Other federal", "SDNR": "State Dept of Natural Resources",
    "SFW": "State Fish & Wildlife", "SPR": "State Parks & Recreation",
    "SLB": "State Land Board (trust land)", "SDOL": "State Dept of Land",
    "SDC": "State Dept of Conservation", "OTHS": "Other state agency",
    "CNTY": "County", "CITY": "City", "REG": "Regional agency",
    "OTHR": "Other", "NGO": "Non-governmental org", "PVT": "Private",
    "TRIB": "Tribal", "UNK": "Unknown",
}
ACCESS = {"OA": "Open access", "RA": "Restricted access", "XA": "Closed to public", "UK": "Unknown access"}
DESIGNATIONS = {
    "NF": "National Forest", "NP": "National Park", "NM": "National Monument",
    "WA": "Wilderness Area", "SP": "State Park", "SW": "State Wilderness",
    "NWR": "National Wildlife Refuge", "REC": "Recreation area",
    "PUB": "Public land", "SRMA": "Special Recreation Management Area",
    "ACEC": "Area of Critical Environmental Concern", "MIL": "Military land",
}


async def manager_at_point(lat: float, lon: float) -> dict | None:
    """Overlapping tracts are common (e.g. generic 'Public land' + a National
    Monument at the same point), so ALL returned tracts are reported: the
    first is the primary manager answer, `all_tracts` carries every
    designation/unit so callers can catch monument/wilderness overlays."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Mang_Name,Own_Name,Own_Type,Mang_Type,Des_Tp,Unit_Nm,GAP_Sts,Pub_Access,Category,State_Nm",
        "returnGeometry": "false",
        "resultRecordCount": "10",
        "f": "json",
    }
    data = await fetch_json("padus", QUERY_URL, params=params)
    feats = data.get("features") or []
    if not feats:
        return None
    tracts = []
    for f in feats:
        attrs = f.get("attributes") or {}
        des = (attrs.get("Des_Tp") or "").strip()
        tracts.append({
            "manager_code": (attrs.get("Mang_Name") or "").strip(),
            "manager_type": attrs.get("Mang_Type"),   # FED/STAT/LOC/PVT/NGO/TRIB
            "designation": DESIGNATIONS.get(des.upper(), des),
            "unit_name": attrs.get("Unit_Nm"),
            "access": ACCESS.get((attrs.get("Pub_Access") or "").upper(), attrs.get("Pub_Access")),
        })
    first = feats[0].get("attributes") or {}
    code = (first.get("Mang_Name") or "").strip()
    return {
        "manager_code": code,
        "manager_name": MANAGER_NAMES.get(code.upper(), code or "Unknown"),
        "owner_code": first.get("Own_Name"),
        "manager_type": first.get("Mang_Type"),
        "designation": tracts[0]["designation"],
        "unit_name": first.get("Unit_Nm"),
        "access": tracts[0]["access"],
        "state": first.get("State_Nm"),
        "all_tracts": tracts,
    }
