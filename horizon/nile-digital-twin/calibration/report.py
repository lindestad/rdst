"""Render docs/calibration-report.html — observed vs. simulated Aswan discharge
with relative RMSE in the title.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from calibration.calibrate import (  # noqa: E402
    OBSERVED_PATH, relative_rmse, rmse, simulated_target_discharge,
)

REPORT_PATH = Path("docs/calibration-report.html")


def main() -> None:
    if not OBSERVED_PATH.exists():
        raise FileNotFoundError(
            f"{OBSERVED_PATH} missing — run `python -m calibration.grdc_fetch` first."
        )
    obs = pd.read_parquet(OBSERVED_PATH)
    sim = simulated_target_discharge({})
    j = sim.merge(obs, on="month", how="inner")

    fig, ax = plt.subplots(figsize=(10, 4), dpi=120)
    ax.plot(j["month"], j["discharge_m3s"], label="GRDC observed", color="#1e3a8a", lw=1.2)
    ax.plot(j["month"], j["sim_m3s"], label="Simulated", color="#f59e0b", lw=1.2)
    ax.set_ylabel("Discharge at Aswan (m³/s)")
    ax.set_title("Nile Digital Twin — calibration against GRDC")
    ax.legend()
    ax.grid(alpha=0.3)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()

    r = rmse(sim, obs)
    rr = relative_rmse(sim, obs)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Nile Twin — Calibration</title>
<style>body{{font-family:system-ui;margin:2em;max-width:900px;color:#0f172a}}</style>
</head><body>
<h1>Nile Digital Twin — calibration report</h1>
<p>Simulated monthly inflow at the Aswan High Dam versus GRDC observed
discharge, 2005–2024.</p>
<p><b>RMSE:</b> {r:.0f} m³/s &nbsp;·&nbsp; <b>Relative RMSE:</b> {rr * 100:.1f}%</p>
<img src="data:image/png;base64,{b64}" style="max-width:100%">
<p><i>Tuned via grid search over source catchment scaling and Sudd
evaporation fraction.</i></p>
</body></html>
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html)
    print(f"wrote {REPORT_PATH} — RMSE {r:.0f} m³/s, relative {rr * 100:.1f}%")


if __name__ == "__main__":
    main()
