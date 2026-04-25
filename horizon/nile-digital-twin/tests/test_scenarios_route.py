from fastapi.testclient import TestClient

from api.app import create_app


def _sample_body():
    return {
        "name": "t",
        "period": ["2020-01", "2020-03"],
        "policy": {
            "reservoirs": {}, "demands": {}, "constraints": {},
            "weights": {"water": 0.4, "food": 0.3, "energy": 0.3},
        },
    }


def test_run_returns_results():
    client = TestClient(create_app())
    r = client.post("/scenarios/run", json=_sample_body())
    assert r.status_code == 200
    body = r.json()
    assert body["results"] is not None
    assert len(body["results"]["kpi_monthly"]) == 3
    assert "score" in body["results"]


def test_save_and_list_and_load():
    client = TestClient(create_app())
    ran = client.post("/scenarios/run", json=_sample_body()).json()
    saved = client.post(f"/scenarios/{ran['id']}/save", json=ran).json()
    assert saved["id"] == ran["id"]

    listed = client.get("/scenarios").json()
    assert any(row["id"] == ran["id"] for row in listed)

    loaded = client.get(f"/scenarios/{ran['id']}").json()
    assert loaded["name"] == "t"


def test_delete():
    client = TestClient(create_app())
    ran = client.post("/scenarios/run", json=_sample_body()).json()
    client.post(f"/scenarios/{ran['id']}/save", json=ran)
    r = client.delete(f"/scenarios/{ran['id']}")
    assert r.status_code == 204


def test_compare_two_scenarios():
    client = TestClient(create_app())
    a = client.post("/scenarios/run", json=_sample_body()).json()
    b_body = _sample_body(); b_body["name"] = "t2"
    b = client.post("/scenarios/run", json=b_body).json()
    client.post(f"/scenarios/{a['id']}/save", json=a)
    client.post(f"/scenarios/{b['id']}/save", json=b)

    r = client.post(
        "/scenarios/compare",
        json={"scenario_ids": [a["id"], b["id"]]},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body["scenarios"].keys()) == {a["id"], b["id"]}
    assert len(body["kpi_deltas"]) == 3
    assert "score_delta" in body
