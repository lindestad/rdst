from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass
class NrsmSimulator:
    """Small adapter around nrsm_py.PreparedScenario."""

    prepared: object

    @classmethod
    def from_yaml(cls, path: Path | str) -> NrsmSimulator:
        nrsm_py = _import_nrsm_py()
        return cls(nrsm_py.PreparedScenario.from_yaml(Path(path)))

    @classmethod
    def from_period(
        cls,
        period_path: Path | str,
        *,
        data_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> NrsmSimulator:
        nrsm_py = _import_nrsm_py()
        prepared = nrsm_py.PreparedScenario.from_period(
            Path(period_path),
            None if data_dir is None else Path(data_dir),
            None if output_dir is None else Path(output_dir),
        )
        return cls(prepared)

    def node_ids(self) -> list[str]:
        return list(self.prepared.node_ids())

    def node_count(self) -> int:
        return int(self.prepared.node_count())

    def horizon_days(self) -> int:
        return int(self.prepared.horizon_days())

    def expected_action_len(self) -> int:
        return int(self.prepared.expected_action_len())

    def summary(self, actions: Sequence[float]) -> dict[str, float]:
        return json.loads(self.prepared.run_actions_summary_json(list(actions)))

    def result(self, actions: Sequence[float]) -> dict:
        return json.loads(self.prepared.run_actions_json(list(actions)))


def _import_nrsm_py() -> object:
    try:
        import nrsm_py
    except ImportError as exc:
        raise RuntimeError(
            "nrsm_py is not installed. Build it with `python -m maturin develop` "
            "from horizon/nrsm/crates/nrsm-py, or run from an environment where "
            "the NRSM Python extension is available."
        ) from exc
    return nrsm_py
