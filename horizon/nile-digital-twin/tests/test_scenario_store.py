from api.scenario_store import ScenarioStore
from simengine.scenario import Policy, Scenario, Weights


def _sample_scenario(name="t") -> Scenario:
    return Scenario(
        name=name, period=["2005-01", "2024-12"],
        policy=Policy(weights=Weights(water=0.4, food=0.3, energy=0.3)),
    )


def test_save_and_list():
    store = ScenarioStore()
    s = _sample_scenario()
    store.save(s)
    ids = [row["id"] for row in store.list()]
    assert s.id in ids


def test_save_and_load():
    store = ScenarioStore()
    s = _sample_scenario()
    store.save(s)
    loaded = store.load(s.id)
    assert loaded.name == s.name


def test_delete():
    store = ScenarioStore()
    s = _sample_scenario()
    store.save(s)
    store.delete(s.id)
    assert all(row["id"] != s.id for row in store.list())
