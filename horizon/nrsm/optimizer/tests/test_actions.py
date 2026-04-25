from __future__ import annotations

from datetime import date

import numpy as np

from nrsm_optimizer.actions import PiecewiseActionSpace


def test_piecewise_action_space_expands_to_daily_row_major_matrix() -> None:
    space = PiecewiseActionSpace(
        node_ids=("a", "b", "c"),
        horizon_days=5,
        interval_days=2,
        controlled_nodes=("b",),
        default_action=1.0,
    )

    matrix = space.expand([0.2, 0.4, 0.6])

    assert matrix.tolist() == [
        [1.0, 0.2, 1.0],
        [1.0, 0.2, 1.0],
        [1.0, 0.4, 1.0],
        [1.0, 0.4, 1.0],
        [1.0, 0.6, 1.0],
    ]
    assert space.flatten([0.2, 0.4, 0.6]) == matrix.reshape(-1).tolist()


def test_piecewise_action_space_writes_one_action_file_per_node(tmp_path) -> None:
    space = PiecewiseActionSpace(
        node_ids=("a", "b"),
        horizon_days=3,
        interval_days=2,
    )

    paths = space.write_action_csvs(
        np.array([0.1, 0.2, 0.3, 0.4]),
        tmp_path,
        start_date=date(2005, 1, 1),
    )

    assert [path.name for path in paths] == ["a.actions.csv", "b.actions.csv"]
    assert paths[0].read_text(encoding="utf-8").splitlines() == [
        "date,optimized",
        "2005-01-01,0.100000",
        "2005-01-02,0.100000",
        "2005-01-03,0.300000",
    ]
