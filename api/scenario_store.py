"""File-backed CRUD for scenarios. One JSON file per scenario under
`data/scenarios/<uuid>.json`. In-process only; not thread-safe — fine for a
single-worker uvicorn deployment."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from api import deps
from simengine.scenario import Scenario


class ScenarioStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else deps.DATA_DIR / "scenarios"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, s: Scenario) -> Scenario:
        s.to_file(self.root / f"{s.id}.json")
        return s

    def load(self, scenario_id: str) -> Scenario:
        p = self.root / f"{scenario_id}.json"
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown scenario: {scenario_id}")
        return Scenario.from_file(p)

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.root.glob("*.json")):
            s = Scenario.from_file(p)
            out.append({
                "id": s.id,
                "name": s.name,
                "created_at": s.created_at,
                "score": s.results.score if s.results else None,
                "period": s.period,
            })
        return out

    def delete(self, scenario_id: str) -> None:
        p = self.root / f"{scenario_id}.json"
        if p.exists():
            p.unlink()
