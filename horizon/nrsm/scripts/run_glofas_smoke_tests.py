# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "cdsapi>=0.7.7",
# ]
# ///
"""Run GloFAS downloader tests.

Default mode is offline and validates request construction/env handling:

    uv run horizon/nrsm/scripts/run_glofas_smoke_tests.py

To run the real one-day EWDS fetch too, set RUN_EWDS_INTEGRATION=1:

    $env:RUN_EWDS_INTEGRATION="1"
    uv run horizon/nrsm/scripts/run_glofas_smoke_tests.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[2]

    unit = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", str(script_dir), "-p", "test_fetch_*.py"],
        cwd=repo_root,
        check=False,
    )
    if unit.returncode != 0:
        return unit.returncode

    if os.environ.get("RUN_EWDS_INTEGRATION") != "1":
        print("Skipping real EWDS fetch. Set RUN_EWDS_INTEGRATION=1 to enable it.")
        return 0

    target = repo_root / "horizon" / "nrsm" / "data" / "raw" / "glofas" / "integration_smoke.grib2"
    submit = subprocess.run(
        [
            sys.executable,
            str(script_dir / "fetch_glofas_smoke.py"),
            "--submit",
            "--target",
            str(target),
        ],
        cwd=repo_root,
        check=False,
    )
    if submit.returncode != 0:
        return submit.returncode
    if not target.exists() or target.stat().st_size == 0:
        print(f"Expected non-empty GloFAS output at {target}", file=sys.stderr)
        return 1

    print(f"Verified non-empty GloFAS output: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
