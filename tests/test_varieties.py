"""Named-variety search: alias resolution + API integration."""
import respx
from httpx import Response

from app import varieties
from app.main import resolve_commodity_terms
from app.sources import mrds
from tests.test_mrds import GML_SAMPLE


def test_resolve_exact_and_aliases():
    assert varieties.resolve("Kentucky agate")["name"] == "Kentucky agate"
    assert varieties.resolve("KY AGATE")["name"] == "Kentucky agate"
    # user-typo alias from the actual request ("holy blue agate")
    assert varieties.resolve("holy blue agate")["name"] == "Holley blue agate"
    assert varieties.resolve("Holly Blue")["name"] == "Holley blue agate"
    assert varieties.resolve("herkimer")["name"] == "Herkimer diamond"
    assert varieties.resolve("not-a-variety") is None


def test_resolve_ignores_punctuation_and_case():
    assert varieties.resolve("  Cave-in-Rock   Fluorite! ") is not None


def test_every_variety_has_required_fields():
    for v in varieties.public_list():
        assert v["name"] and v["blurb"] and v["note"]
        assert v["codes"], f"{v['name']} has no base codes"
        if v["region"] is not None:
            w, s, e, n = v["region"]["bbox"]
            assert -180 <= w < e <= 180 and -90 <= s < n <= 90, f"bad bbox for {v['name']}"
            assert v["region"]["label"]


def test_resolve_commodity_terms_mixes_names_codes_varieties():
    codes, hits, unknown = resolve_commodity_terms("Gold, kentucky agate, REE, gibberish!!")
    assert "AU" in codes and "GEM" in codes and "REE" in codes
    assert [h["name"] for h in hits] == ["Kentucky agate"]
    assert unknown == ["gibberish!!"]
    # dedup: variety codes appearing twice collapse
    codes2, _, _ = resolve_commodity_terms("kentucky agate, fire agate")
    assert codes2.count("GEM") == 1


def test_codes_to_names_translation():
    assert mrds.codes_to_names(" CU AU") == "Copper, Gold"
    assert mrds.codes_to_names("GEM STN_C") == "Gemstone, Stone (crushed)"
    assert mrds.codes_to_names("F") == "Fluorite"
    assert mrds.codes_to_names("XYZQ") == "XYZQ"  # unknown codes pass through raw


@respx.mock
def test_sites_variety_term_filters_and_warns(client):
    respx.get(mrds.WFS_URL).mock(return_value=Response(200, text=GML_SAMPLE))
    r = client.get("/api/sites", params={
        "bbox": "-113.5,33.0,-111.5,34.5",
        "commodities": "holy blue agate",  # GEM+SIL — sample sites are CU/AU/AG, so 0 match
    })
    body = r.json()
    assert body["features"] == []
    assert any("Holley blue agate" in w for w in body["warnings"])


def test_config_exposes_varieties(client):
    body = client.get("/api/config").json()
    names = [v["name"] for v in body["varieties"]]
    assert "Kentucky agate" in names and "Holley blue agate" in names
    ky = next(v for v in body["varieties"] if v["name"] == "Kentucky agate")
    assert ky["region"]["bbox"][0] < ky["region"]["bbox"][2]


_RECORD = {
    "id": "https://mrdata.usgs.gov/mrds/record/10046211",
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-110.75, 32.5]},
    "properties": {
        "name": [{"line": "1", "name": "East Side Mine", "status": "Current",
                  "inserted_by": "x", "insert_date": "y"},
                 {"line": "2", "name": "East Side No. 2", "status": "Previous"}],
        "commodity": [
            {"line": "1", "commod": "Silver", "code": "AG", "commod_tp": "Metallic",
             "import": "Primary", "inserted_by": "x"},
            {"line": "2", "commod": "Copper", "code": "CU", "commod_tp": "Metallic",
             "import": "Secondary"},
        ],
        "material": [{"rec": "1", "ore_gangue": "Ore", "material": "Galena", "recid": "1"}],
        "rock": [],
        "deposits": {"dep_id": "10046211", "dev_st": "Past Producer", "dep_tp": "Vein",
                     "oper_tp": "Unknown", "prod_size": "S", "deposit_size": "S"},
        "location": {"country": "United States", "state_prov": "Arizona", "county": "Pima"},
        "comment": [{"ctg": "Deposit", "cmt": "Old workings."}],
    },
}


@respx.mock
def test_site_detail_transform(client):
    respx.get(mrds.RECORD_URL.format(dep_id="10046211")).mock(
        return_value=Response(200, json=_RECORD))
    r = client.get("/api/sites/10046211")
    assert r.status_code == 200
    d = r.json()
    assert [n["name"] for n in d["names"]] == ["East Side Mine", "East Side No. 2"]
    assert d["commodities"][0]["commod"] == "Silver"
    assert d["commodities"][0]["import"] == "Primary"
    # audit fields stripped
    assert "inserted_by" not in d["names"][0]
    assert "inserted_by" not in d["commodities"][0]
    assert d["deposit"]["dev_st"] == "Past Producer"
    assert d["materials"][0]["material"] == "Galena"
    assert d["location"]["county"] == "Pima"
    assert d["url"].endswith("dep_id=10046211")


def test_site_detail_rejects_non_numeric(client):
    assert client.get("/api/sites/abc").status_code == 400
    assert client.get("/api/sites/..%2F..%2Fetc").status_code in (400, 404)


_RECORD_DICT_SECTIONS = {
    "id": "https://mrdata.usgs.gov/mrds/record/10098130",
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-112.0, 33.6]},
    "properties": {
        # single-entry sections arrive as DICTS, not lists (live MRDS quirk)
        "name": {"line": "1", "name": "Sand and Gravel Quarry", "status": "Current"},
        "commodity": {"line": "1", "commod": "Sand and Gravel, Construction",
                      "code": "SDG", "import": "Primary"},
        "material": {"rec": "1", "ore_gangue": "Ore", "material": "Sand and Gravel"},
        "rock": [{"rock_line": "4", "rock_cls": "Host"}],
        "deposits": {"dep_id": "10098130", "dev_st": "Past Producer"},
        "location": {"line": "1", "country": "United States", "state_prov": "Arizona"},
        "comment": {"line": "1", "ctg": "Development", "cmt_txt": "UNCLEAR."},
    },
}


@respx.mock
def test_site_detail_handles_dict_shaped_sections(client):
    """Regression: single-entry MRDS sections are dicts -> 500 before _aslist."""
    respx.get(mrds.RECORD_URL.format(dep_id="10098130")).mock(
        return_value=Response(200, json=_RECORD_DICT_SECTIONS))
    r = client.get("/api/sites/10098130")
    assert r.status_code == 200
    d = r.json()
    assert d["names"][0]["name"] == "Sand and Gravel Quarry"
    assert d["commodities"][0]["code"] == "SDG"
    assert d["location"]["state_prov"] == "Arizona"
    assert d["comment"][0]["cmt_txt"] == "UNCLEAR."
