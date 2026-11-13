"""Land-status verdict logic with mocked upstreams."""
import pytest
import respx
from httpx import Response

from app import land_status
from app.sources import blm, geocode, padus, parcels

SMA_URL = blm.SMA_QUERY_URL
PADUS_URL = padus.QUERY_URL
CENSUS_URL = geocode.CENSUS_URL
CLAIMS_URL = blm.CLAIMS_ACTIVE_URL
MARICOPA_URL = parcels.COUNTY_REST[("AZ", "Maricopa")]["url"]


def _sma(code, unit=None):
    return {"features": [{"attributes": {"ADMIN_AGENCY_CODE": code,
                                         "ADMIN_UNIT_NAME": unit,
                                         "ADMIN_DEPT_CODE": code, "ADMIN_ST": "AZ"}}]}


def _census(state="AZ", state_name="Arizona", county="Maricopa County"):
    return {"result": {"geographies": {
        "States": [{"STUSAB": state, "NAME": state_name}],
        "Counties": [{"NAME": county}],
    }}}


EMPTY = {"features": []}


@pytest.mark.anyio
@respx.mock
async def test_blm_point_is_public_with_collecting_note():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("BLM", "Bureau of Land Management")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(county="Mohave County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(34.5, -113.5)
    assert r["verdict"] == "public"
    assert r["manager"] == "Bureau of Land Management"
    assert any("43 CFR 8365.1-5" in n for n in r["notes"])


@pytest.mark.anyio
@respx.mock
async def test_private_point_returns_owner_and_links():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("PVT")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census()))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(MARICOPA_URL).mock(return_value=Response(200, json={"features": [{"attributes": {
        "APN": "501-33-011S", "OwnerName": "SOME OWNER LLC",
        "PropertyFullStreetAddress": "123 Somewhere", "AssessorWebLink": None}}]}))
    r = await land_status.check(33.61, -112.34)
    assert r["verdict"] == "private"
    assert r["owner"] == "SOME OWNER LLC"
    assert r["apn"] == "501-33-011S"
    labels = [l["label"] for l in r["owner_lookup"]]
    assert any("assessor" in l.lower() for l in labels)
    assert any("NETR" in l for l in labels)


@pytest.mark.anyio
@respx.mock
async def test_az_state_trust_gets_no_rockhounding_warning():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("ST", "State Trust Land")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census()))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(33.0, -112.0)
    assert r["verdict"] == "state_trust"
    assert any("rockhounding is NOT allowed" in n for n in r["notes"])


@pytest.mark.anyio
@respx.mock
async def test_active_claim_adds_warning():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("BLM")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(county="Mohave County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json={"features": [{"attributes": {
        "CSE_NAME": "UNION MINE", "CSE_TYPE_NR": "384101",
        "CSE_DISP": "Active", "CSE_NR": "AZ105"}}]}))
    r = await land_status.check(34.5, -113.5)
    assert any("UNION MINE" in n for n in r["notes"])
    assert r["claims"][0]["case_type"] == "Lode Claim"


@pytest.mark.anyio
@respx.mock
async def test_sma_down_degrades_to_unverified_not_crash():
    respx.get(SMA_URL).mock(return_value=Response(500))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census()))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(34.5, -113.5)
    assert r["verdict"] == "unknown"
    assert any("unreachable" in n for n in r["notes"])


@pytest.mark.anyio
@respx.mock
async def test_nps_point_is_restricted():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("NPS", "Grand Canyon NP")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(county="Coconino County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(36.1, -112.1)
    assert r["verdict"] == "restricted"


@pytest.mark.anyio
@respx.mock
async def test_und_agency_code_treated_as_private_not_public():
    """Eastern US: SMA returns ADMIN_AGENCY_CODE='UND' (Undetermined) — must
    NOT be presented as public land (regression: rural KY showed 'public')."""
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("UND", "Undetermined")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(
        state="KY", state_name="Kentucky", county="Breckinridge County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(37.77, -86.43)
    assert r["verdict"] == "private"
    assert any("NETR" in l["label"] for l in r["owner_lookup"])
    assert any("PVA" in n or "subscription" in n for n in r["notes"])  # KY ceiling note


def _padus(mang="BLM", mtype="FED", des="NM", unit="Some National Monument"):
    return {"features": [{"attributes": {
        "Mang_Name": mang, "Own_Name": mang, "Own_Type": mtype, "Mang_Type": mtype,
        "Des_Tp": des, "Unit_Nm": unit, "GAP_Sts": "2", "Pub_Access": "OA",
        "Category": "Fee", "State_Nm": "AZ"}}]}


@pytest.mark.anyio
@respx.mock
async def test_blm_inside_national_monument_downgrades_to_restricted():
    """BLM surface inside a National Monument must NOT show the green
    'collecting generally allowed' verdict."""
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("BLM", "BLM")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=_padus(des="NM")))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(county="Mohave County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(35.0, -113.6)
    assert r["verdict"] == "restricted"
    assert "National Monument" in r["verdict_label"]
    assert any("special designation" in n or "designations" in n for n in r["notes"])


@pytest.mark.anyio
@respx.mock
async def test_point_outside_us_is_unknown_not_private():
    """Ocean / foreign points: no SMA tract, no PAD-US, no Census state ->
    must not be asserted as 'private property'."""
    respx.get(SMA_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json={"result": {"geographies": {}}}))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(20.0, -40.0)  # mid-Atlantic
    assert r["verdict"] == "unknown"
    assert any("outside US" in n for n in r["notes"])


@pytest.mark.anyio
@respx.mock
async def test_unmapped_sma_code_is_not_public():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("OTFE", "Some Fed Thing")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=EMPTY))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census()))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(34.0, -112.0)
    assert r["verdict"] != "public"


@pytest.mark.anyio
@respx.mock
async def test_padus_outage_adds_unverified_note():
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("BLM", "BLM")))
    respx.get(PADUS_URL).mock(return_value=Response(500))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(county="Mohave County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(34.5, -113.5)
    assert any("PAD-US" in n and "unreachable" in n for n in r["notes"])


@pytest.mark.anyio
@respx.mock
async def test_padus_outage_blocks_private_assertion():
    """SMA says PVT but PAD-US is down: could be a state park only PAD-US
    knows about -> must NOT assert 'private'."""
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("PVT")))
    respx.get(PADUS_URL).mock(return_value=Response(500))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census()))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(33.6, -112.3)
    assert r["verdict"] == "unknown"


@pytest.mark.anyio
@respx.mock
async def test_overlapping_padus_tracts_catch_monument():
    """PAD-US returns a generic 'Public land' tract FIRST and the National
    Monument tract second — the monument must still downgrade the verdict."""
    two_tracts = {"features": [
        {"attributes": {"Mang_Name": "BLM", "Mang_Type": "FED", "Des_Tp": "PUB",
                        "Unit_Nm": "Lower Sonoran public land", "Pub_Access": "OA"}},
        {"attributes": {"Mang_Name": "BLM", "Mang_Type": "FED", "Des_Tp": "NM",
                        "Unit_Nm": "Sonoran Desert National Monument", "Pub_Access": "OA"}},
    ]}
    respx.get(SMA_URL).mock(return_value=Response(200, json=_sma("BLM", "BLM")))
    respx.get(PADUS_URL).mock(return_value=Response(200, json=two_tracts))
    respx.get(CENSUS_URL).mock(return_value=Response(200, json=_census(county="Maricopa County")))
    respx.get(CLAIMS_URL).mock(return_value=Response(200, json=EMPTY))
    r = await land_status.check(32.98, -112.47)
    assert r["verdict"] == "restricted"
    assert "National Monument" in r["verdict_label"]
