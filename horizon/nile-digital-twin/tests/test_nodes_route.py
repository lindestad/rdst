from fastapi.testclient import TestClient

from api.app import create_app


def test_list_nodes_returns_geojson():
    r = TestClient(create_app()).get("/nodes")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2


def test_get_single_node_config():
    r = TestClient(create_app()).get("/nodes/gerd")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "gerd"
    assert body["type"] == "reservoir"
    assert body["storage_capacity_mcm"] == 74000


def test_get_unknown_node_404():
    r = TestClient(create_app()).get("/nodes/does_not_exist")
    assert r.status_code == 404


def test_timeseries_route():
    r = TestClient(create_app()).get(
        "/nodes/lake_victoria_outlet/timeseries"
        "?start=2020-01&end=2020-02&vars=precip_mm,pet_mm"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == ["2020-01", "2020-02"]
    assert body["values"]["precip_mm"] == [50.0, 60.0]
    assert body["values"]["pet_mm"] == [150.0, 160.0]
    assert "temp_c" not in body["values"]
