"""MRDS GML parsing + commodity/status filtering (pure functions, no network)."""
import pytest

from app.sources import mrds

GML_SAMPLE = """<?xml version='1.0' encoding="UTF-8" ?>
<wfs:FeatureCollection
   xmlns:ms="http://mapserver.gis.umn.edu/mapserver"
   xmlns:wfs="http://www.opengis.net/wfs"
   xmlns:gml="http://www.opengis.net/gml">
  <gml:featureMember>
    <ms:mrds gml:id="mrds.10046211">
      <gml:boundedBy><gml:Envelope srsName="EPSG:4326">
        <gml:lowerCorner>33.6 -112.0</gml:lowerCorner><gml:upperCorner>33.6 -112.0</gml:upperCorner>
      </gml:Envelope></gml:boundedBy>
      <ms:geometry><gml:Point srsName="EPSG:4326"><gml:pos>33.65947 -112.03653</gml:pos></gml:Point></ms:geometry>
      <ms:dep_id>10046211</ms:dep_id>
      <ms:site_name>Webb Group</ms:site_name>
      <ms:dev_stat>Past Producer</ms:dev_stat>
      <ms:code_list> CU AU</ms:code_list>
      <ms:url>https://mrdata.usgs.gov/mrds/show-mrds.php?dep_id=10046211</ms:url>
    </ms:mrds>
  </gml:featureMember>
  <gml:featureMember>
    <ms:mrds gml:id="mrds.2">
      <ms:geometry><gml:Point><gml:pos>34.0 -113.0</gml:pos></gml:Point></ms:geometry>
      <ms:dep_id>2</ms:dep_id>
      <ms:site_name>Silver Spot</ms:site_name>
      <ms:dev_stat>Occurrence</ms:dev_stat>
      <ms:code_list> AG</ms:code_list>
    </ms:mrds>
  </gml:featureMember>
</wfs:FeatureCollection>"""


def test_parse_gml_extracts_sites():
    sites, members = mrds.parse_gml(GML_SAMPLE)
    assert len(sites) == 2
    assert members == 2
    first = sites[0]
    assert first["dep_id"] == "10046211"
    assert first["site_name"] == "Webb Group"
    assert first["dev_stat"] == "Past Producer"
    # gml:pos is 'lat lon'
    assert first["lat"] == pytest.approx(33.65947)
    assert first["lon"] == pytest.approx(-112.03653)


def test_parse_gml_bad_xml_raises():
    from app.upstream import UpstreamError
    with pytest.raises(UpstreamError):
        mrds.parse_gml("<not-closed")


def test_filter_by_commodity_handles_leading_space_code_list():
    sites, members = mrds.parse_gml(GML_SAMPLE)
    gold = mrds.filter_sites(sites, ["AU"], [])
    assert [s["site_name"] for s in gold] == ["Webb Group"]


def test_filter_by_status():
    sites, members = mrds.parse_gml(GML_SAMPLE)
    occ = mrds.filter_sites(sites, [], ["Occurrence"])
    assert [s["site_name"] for s in occ] == ["Silver Spot"]


def test_filter_no_criteria_returns_all():
    sites, members = mrds.parse_gml(GML_SAMPLE)
    assert len(mrds.filter_sites(sites, [], [])) == 2


def test_resolve_commodity_names_and_raw_codes():
    assert mrds.resolve_commodity("Gold") == "AU"
    assert mrds.resolve_commodity("  copper ") == "CU"
    assert mrds.resolve_commodity("REE") == "REE"          # raw code passthrough
    assert mrds.resolve_commodity("not a mineral!") is None
    assert mrds.resolve_commodity("") is None


def test_to_geojson_shape():
    sites, members = mrds.parse_gml(GML_SAMPLE)
    gj = mrds.to_geojson(sites, truncated=True)
    assert gj["type"] == "FeatureCollection"
    assert gj["truncated"] is True
    f = gj["features"][0]
    assert f["geometry"]["coordinates"] == [pytest.approx(-112.03653), pytest.approx(33.65947)]
    assert f["properties"]["commodities"] == "CU AU"  # leading space stripped
    # site without ms:url still gets a synthesized record link
    assert "dep_id=2" in gj["features"][1]["properties"]["url"]


def test_parse_gml_counts_dropped_members():
    """Members without usable gml:pos are dropped from sites but still counted
    (truncation detection uses the raw member count)."""
    broken = GML_SAMPLE.replace("<gml:pos>34.0 -113.0</gml:pos>", "<gml:pos></gml:pos>")
    sites, members = mrds.parse_gml(broken)
    assert len(sites) == 1
    assert members == 2
