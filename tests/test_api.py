"""API endpoint tests with mocked upstreams (respx)."""
import json

import pytest
import respx
from httpx import Response

from app.sources import blm, mrds, padus, usmin
from tests.test_mrds import GML_SAMPLE


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_config_lists_commodities_and_tiles(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert "Gold" in body["commodities"]
    assert body["ownership"]["tiles"].startswith("https://gis.blm.gov")
    assert body["mindat_enabled"] in (True, False)


@pytest.mark.parametrize("bad", ["", "1,2,3", "abc", "-200,0,10,10", "10,10,-10,20", "-180,-90,180,90"])
def test_sites_rejects_bad_bbox(client, bad):
    r = client.get("/api/sites", params={"bbox": bad})
    assert r.status_code == 400


@respx.mock
def test_sites_parses_filters_and_reports_unknown_commodity(client):
    respx.get(mrds.WFS_URL).mock(return_value=Response(200, text=GML_SAMPLE))
    r = client.get("/api/sites", params={
        "bbox": "-113.5,33.0,-111.5,34.5",
        "commodities": "Gold,notreal!!",
        "statuses": "Past Producer",
    })
    assert r.status_code == 200
    body = r.json()
    assert [f["properties"]["name"] for f in body["features"]] == ["Webb Group"]
    assert body["truncated"] is False
    assert "notreal!!" in body["warnings"][0]


@respx.mock
def test_sites_upstream_down_returns_502(client):
    respx.get(mrds.WFS_URL).mock(return_value=Response(500, text="boom"))
    r = client.get("/api/sites", params={"bbox": "-113,33,-112,34"})
    assert r.status_code == 502
    assert "mrds" in r.json()["detail"]


def _usmin_point_fc():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-110.8, 33.4]},
            "properties": {"Ftr_Type": "Adit", "Ftr_Name": None, "State": "AZ",
                           "County": "Gila", "Topo_Name": "Globe", "Topo_Date": 1945,
                           "Remarks": None},
        }],
    }


def _usmin_polygon_fc():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[-110.9, 33.39], [-110.89, 33.39],
                                          [-110.89, 33.40], [-110.9, 33.40], [-110.9, 33.39]]]},
            "properties": {"Ftr_Type": "Tailings - Pond", "Ftr_Name": "Big Tailings",
                           "State": "AZ", "County": "Gila", "Topo_Name": "Globe",
                           "Topo_Date": 1945, "Remarks": None},
        }],
    }


@respx.mock
def test_mines_all_uses_points_layer_only(client):
    points = respx.get(usmin.POINTS_URL).mock(return_value=Response(200, json=_usmin_point_fc()))
    polys = respx.get(usmin.POLYGONS_URL).mock(return_value=Response(200, json=_usmin_polygon_fc()))
    r = client.get("/api/mines", params={"bbox": "-111,33,-110.5,33.6"})
    assert r.status_code == 200
    assert points.called and not polys.called
    assert [f["properties"]["ftr_type"] for f in r.json()["features"]] == ["Adit"]


@respx.mock
def test_mines_tailings_merges_polygon_centroids(client):
    respx.get(usmin.POINTS_URL).mock(return_value=Response(200, json={"type": "FeatureCollection", "features": []}))
    respx.get(usmin.POLYGONS_URL).mock(return_value=Response(200, json=_usmin_polygon_fc()))
    r = client.get("/api/mines", params={"bbox": "-111,33,-110.5,33.6", "tailings_only": "1"})
    body = r.json()
    assert len(body["features"]) == 1
    f = body["features"][0]
    assert f["geometry"]["type"] == "Point"
    assert f["properties"]["area_feature"] is True
    assert f["properties"]["name"] == "Big Tailings"
    # centroid inside the source polygon
    lon, lat = f["geometry"]["coordinates"]
    assert -110.9 < lon < -110.89 and 33.39 < lat < 33.40


@respx.mock
def test_claims_maps_type_codes(client):
    fc = {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
        "properties": {"CSE_NAME": "UNION MINE", "CSE_TYPE_NR": "384101",
                       "CSE_DISP": "Active", "CSE_NR": "AZ105223168", "RCRD_ACRS": 20.66},
    }]}
    respx.get(blm.CLAIMS_ACTIVE_URL).mock(return_value=Response(200, json=fc))
    r = client.get("/api/claims", params={"bbox": "-114,34,-113,35"})
    p = r.json()["features"][0]["properties"]
    assert p["case_type"] == "Lode Claim"
    assert p["serial"] == "AZ105223168"


def test_laws_index_and_state(client):
    r = client.get("/api/laws")
    codes = [s["code"] for s in r.json()["states"]]
    assert "AZ" in codes and "KY" in codes
    az = client.get("/api/laws/az").json()
    assert az["name"] == "Arizona"
    # the AZ trust-land correction must be present — this is the app's key legal fact
    assert "not allowed on Arizona" in json.dumps(az) or "NOT open to rockhounding" in json.dumps(az)
    assert client.get("/api/laws/ZZ").status_code == 404


def test_mindat_disabled_returns_503(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "mindat_api_key", "")
    r = client.get("/api/mindat/localities", params={"bbox": "-113,33,-112,34"})
    assert r.status_code == 503
    assert "MSCOUT_MINDAT_API_KEY" in r.json()["detail"]


@respx.mock
def test_export_gpx_escapes_and_includes_sites(client):
    respx.get(mrds.WFS_URL).mock(return_value=Response(200, text=GML_SAMPLE))
    r = client.get("/api/export.gpx", params={"bbox": "-113.5,33.0,-111.5,34.5"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/gpx+xml")
    assert "<wpt" in r.text and "Webb Group" in r.text


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Mineral Scout" in r.text
