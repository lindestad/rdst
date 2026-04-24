from fastapi.testclient import TestClient

from api.app import create_app


def test_ndvi_overlay_returns_columns():
    r = TestClient(create_app()).get("/overlays/ndvi/gezira?start=2020-01&end=2020-02")
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == ["2020-01", "2020-02"]
    assert "ndvi_mean" in body["values"]
    assert body["values"]["ndvi_mean"] == [0.3, 0.4]


def test_unknown_zone_404():
    r = TestClient(create_app()).get("/overlays/ndvi/no_such_zone")
    assert r.status_code == 404
