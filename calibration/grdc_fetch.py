"""Pull monthly observed discharge at the calibration target (default: Aswan).

Sources, in order of preference:
1. A GRDC-mirrored CSV URL provided via env var GRDC_ASWAN_CSV_URL — team-
   authenticated download, real data.
2. A fallback climatology derived from Sutcliffe & Parks 1999 (updated).
   Same value every year for a given month. Good enough for a RMSE sanity
   check but not a substitute for real GRDC data when you actually calibrate.

Writes `data/observed/aswan_discharge.parquet` with columns (`month`, `discharge_m3s`).
"""
from __future__ import annotations

import os
from io import StringIO
from pathlib import Path

import pandas as pd

OUT_PATH = Path("data/observed/aswan_discharge.parquet")

# Monthly climatology at Aswan (m³/s), rounded from Sutcliffe & Parks 1999.
_FALLBACK_CSV = """month,discharge_m3s
1,900
2,700
3,550
4,450
5,500
6,900
7,2500
8,6500
9,7500
10,4500
11,1800
12,1100
"""


def fetch(start: str = "2005-01", end: str = "2024-12") -> pd.DataFrame:
    url = os.environ.get("GRDC_ASWAN_CSV_URL")
    if url:
        import requests
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text), parse_dates=["month"])
    else:
        clim = pd.read_csv(StringIO(_FALLBACK_CSV))
        months = pd.date_range(f"{start}-01", f"{end}-01", freq="MS")
        df = pd.DataFrame({
            "month": months,
            "discharge_m3s": clim.set_index("month").loc[months.month, "discharge_m3s"].values,
        })
    df = df[(df["month"] >= f"{start}-01") & (df["month"] <= f"{end}-01")]
    return df.reset_index(drop=True)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = fetch()
    df.to_parquet(OUT_PATH, index=False)
    src = "real (via GRDC_ASWAN_CSV_URL)" if os.environ.get("GRDC_ASWAN_CSV_URL") else "climatology fallback"
    print(f"wrote {OUT_PATH} ({len(df)} rows, source: {src})")


if __name__ == "__main__":
    main()
