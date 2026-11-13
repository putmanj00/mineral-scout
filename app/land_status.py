"""Combine BLM SMA + PAD-US + Census + BLM claims + county parcels into one
land-status answer for a point: who manages it, can you likely collect, and
if private, how to find the owner.

Verdict rules of thumb (conservative by design):
- Only BLM/USFS produce a 'public — collecting generally allowed' verdict,
  and a PAD-US special designation (monument/wilderness) downgrades it.
- SMA codes PVT/UND/empty mean 'no public manager identified', not 'public'.
- 'private' is only asserted for points inside the US (Census resolved a
  state); open ocean / outside-US points come back 'unknown'.
- Unknown/unmapped manager codes come back 'unknown', never green.
"""
import asyncio

from . import laws
from .sources import blm, geocode, padus, parcels
from .upstream import UpstreamError

_FED_OPEN = {"BLM": "blm", "USFS": "usfs", "FS": "usfs"}
_FED_CLOSED = {"NPS", "USFW", "FWS", "DOD", "DOE", "BOR", "COE", "USBR", "USACE"}
_TRIBAL = {"BIA", "TRIB"}
_NO_MANAGER = {"", "PVT", "UND"}

# PAD-US designations where collecting is prohibited or heavily restricted
# even when the surface manager is BLM/USFS.
_RESTRICTED_DESIGNATIONS = {
    "National Monument", "Wilderness Area", "State Wilderness",
    "Wilderness Study Area", "Area of Critical Environmental Concern",
    "National Park", "Research Natural Area",
}

_ERR = object()


async def _quiet(coro):
    try:
        return await coro
    except UpstreamError:
        return _ERR


def _open_label(kind: str) -> str:
    if kind == "blm":
        return "Public (BLM) — casual collecting generally allowed (verify)"
    return "Public (Forest Service) — hobby collecting usually allowed (check ranger district)"


async def check(lat: float, lon: float) -> dict:
    sma, pad, geo, claims = await asyncio.gather(
        _quiet(blm.sma_at_point(lat, lon)),
        _quiet(padus.manager_at_point(lat, lon)),
        _quiet(geocode.state_county(lat, lon)),
        _quiet(blm.claims_at_point(lat, lon)),
    )

    notes: list[str] = []
    sources: list[str] = []
    sma_err, pad_err, claims_err = sma is _ERR, pad is _ERR, claims is _ERR
    if sma_err:
        sma = None
        notes.append("BLM land-ownership service unreachable — verdict is unverified; "
                     "check again later or at the BLM SMA map directly.")
    else:
        sources.append("BLM SMA")
    if pad_err:
        pad = None
        notes.append("PAD-US protected-areas service unreachable — special designations "
                     "(monuments, wilderness, parks) could not be checked.")
    elif pad:
        sources.append("PAD-US 4.1")
    if geo is _ERR:
        geo = None

    state_code = (geo or {}).get("state_code")
    agency = ((sma or {}).get("agency_code") or "").upper()

    verdict, verdict_label = "unknown", "Unknown — verify locally"
    manager = unit = None

    if agency and agency not in _NO_MANAGER:
        manager, unit = sma["agency_name"], sma.get("unit_name")
        if agency in _FED_OPEN:
            kind = _FED_OPEN[agency]
            verdict, verdict_label = "public", _open_label(kind)
            notes.append(laws.FEDERAL["blm_casual" if kind == "blm" else "usfs_hobby"]["summary"])
        elif agency in _TRIBAL:
            verdict, verdict_label = "restricted", "Tribal land — permission required"
            notes.append("Tribal land is closed to collecting without tribal government permission.")
        elif agency in _FED_CLOSED:
            verdict, verdict_label = "restricted", "Federal land — collecting restricted/prohibited"
            notes.append("This agency's land (parks/refuges/military/reclamation) is generally "
                         "closed to mineral collecting. See the law panel.")
        elif "ST" in agency:
            verdict, verdict_label = "state_trust", "State land — special rules"
            _state_trust_note(notes, state_code)
        elif agency == "LG":
            verdict, verdict_label = "restricted", "Local government land"
            notes.append("County/city land — collecting normally needs local permission.")
        else:
            verdict_label = f"Managed by {manager} — rules unknown, check locally"
    elif pad:
        manager, unit = pad["manager_name"], pad.get("unit_name")
        mt = (pad.get("manager_type") or "").upper()
        code = (pad.get("manager_code") or "").upper()
        if mt == "FED" and code in _FED_OPEN:
            kind = _FED_OPEN[code]
            verdict, verdict_label = "public", _open_label(kind)
            notes.append(laws.FEDERAL["blm_casual" if kind == "blm" else "usfs_hobby"]["summary"])
        elif mt == "FED":
            verdict, verdict_label = "restricted", "Federal land — collecting restricted/prohibited"
        elif mt == "STAT":
            verdict, verdict_label = "state_trust", "State land — special rules"
            _state_trust_note(notes, state_code)
        elif mt in ("LOC", "DIST"):
            verdict, verdict_label = "restricted", "Local government land"
            notes.append("County/city land — collecting normally needs local permission.")
        elif mt == "TRIB":
            verdict, verdict_label = "restricted", "Tribal land — permission required"
        else:
            verdict_label = f"Managed by {manager} — rules unknown, check locally"
        if pad.get("access") == "Closed to public":
            notes.append("PAD-US marks this tract closed to public access.")
    elif not sma_err and not pad_err and state_code:
        verdict, verdict_label = "private", "Private property — ask the owner"
    elif not state_code:
        notes.append("Point is outside US data coverage (no state resolved) — land-status "
                     "sources here are US-only.")

    # Special-designation downgrade: BLM/USFS surface inside a monument or
    # wilderness is NOT open to casual collecting. PAD-US returns overlapping
    # tracts (a generic 'Public land' tract can sit above a Monument tract),
    # so scan ALL of them, not just the first.
    designation = (pad or {}).get("designation")
    restricted_tract = next(
        (t for t in (pad or {}).get("all_tracts", [])
         if t.get("designation") in _RESTRICTED_DESIGNATIONS),
        None)
    if verdict == "public" and restricted_tract:
        designation = restricted_tract["designation"]
        verdict = "restricted"
        verdict_label = f"{designation} — collecting prohibited or heavily restricted"
        notes.insert(0, f"This tract is inside a {designation} "
                        f"({restricted_tract.get('unit_name') or 'unnamed unit'}): casual-collecting "
                        "rules do NOT apply in most special designations. Verify with the managing office.")

    claim_list = []
    if claims_err:
        notes.append("Mining-claims check unavailable right now — verify claim status via BLM MLRS.")
    elif claims:
        claim_list = claims
        names = ", ".join(f"{c['name']} ({c['case_type']})" for c in claims[:5])
        notes.append(f"Inside active mining claim(s): {names}. The claimed mineral belongs "
                     "to the claimant — do not collect it without their permission.")

    result = {
        "verdict": verdict,
        "verdict_label": verdict_label,
        "manager": manager,
        "unit": unit,
        "designation": designation,
        "state_code": state_code,
        "state_name": (geo or {}).get("state_name"),
        "county": (geo or {}).get("county"),
        "claims": claim_list,
        "notes": notes,
        "sources": sources,
        "disclaimer": laws.DISCLAIMER,
        "trespass_note": laws.TRESPASS_NOTE,
        "owner_lookup": [],
        "owner": None,
        "apn": None,
    }

    if verdict == "private":
        lookup = await parcels.owner_lookup(lat, lon, state_code, (geo or {}).get("county"))
        result["owner"] = lookup["owner"]
        result["apn"] = lookup["apn"]
        result["owner_lookup"] = lookup["links"]
        result["notes"].extend(lookup["notes"])
    return result


def _state_trust_note(notes: list[str], state_code: str | None) -> None:
    if state_code == "AZ":
        notes.append("Arizona State Trust land: rockhounding is NOT allowed — the $15 "
                     "recreational permit does not cover mineral collecting, and entry "
                     "without a permit is trespass. See the AZ law panel.")
    else:
        notes.append("State-managed land (park/trust/wildlife) — many states require a "
                     "permit or prohibit collecting. Check the state law panel.")
