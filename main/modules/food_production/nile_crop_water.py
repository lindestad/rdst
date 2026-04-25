"""
Nile Basin Agricultural Water Demand — Daily Time Series, 1950–2026
====================================================================
Estimates the daily gross agricultural water withdrawal (m³/s) for each
zone defined in nile.yaml, using:

  1. ERA5-Land ET₀ (monthly means, interpolated to daily)  — already cached
     in era5_cache/ by copernicus_egypt_agriculture.py.

  2. Zone-specific crop calendar Kc values from nile_crop_config.yaml.

  3. CGLS-LC100 v3 (2015–2019) 5-year mean cropland area from cgls_cache/,
     computed via nile_agri_area.py.

  4. Zone-specific irrigation efficiency from nile_crop_config.yaml.

Water demand formulas
---------------------
  ET_crop  [mm/day]  = Kc(month) × ET₀
  V_net    [m³/day]  = ET_crop × 10 × area_ha
                       (total water consumed by crops — from rain OR irrigation,
                        regardless of source)
  Q        [m³/s]    = V_net / 86 400

Food productivity
-----------------
  A constant gross crop water productivity (kg food / m³ withdrawn) is
  assigned per zone via nile_crop_config.yaml.  It is shown in the plot
  legend but not used in the water demand calculation itself.

Inputs
------
  era5_cache/{zone}_1950_2026.csv  — monthly ET₀ (mm/day, positive)
  cgls_cache/{zone}_20*_crops_frac.npy — CGLS window arrays
  cgls_cache/{zone}_20*_crops_frac.meta.npy — pixel size + centre lat
  nile.yaml                        — node coordinates
  nile_crop_config.yaml            — crop types and zone parameters

Outputs
-------
  nile_water_demand.png   — two-panel daily time series 1950–2026 (m³/s)
  nile_water_demand.csv   — daily Q (total crop ET) per zone
"""

import math
import pathlib
import re

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy.interpolate import PchipInterpolator

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = pathlib.Path(__file__).parent
ERA5_DIR   = ROOT / "era5_cache"
CGLS_DIR   = ROOT / "cgls_cache"
NILE_YAML  = ROOT / "nile.yaml"
CROP_YAML  = ROOT / "nile_crop_config.yaml"
OUT_PNG    = ROOT / "nile_water_demand.png"
OUT_CSV    = ROOT / "nile_water_demand.csv"

YEAR_FROM, YEAR_TO = 1950, 2026
R_EARTH = 6_378_137.0   # WGS-84 semi-major axis (m)


# ── Config loaders ────────────────────────────────────────────────────────────

def load_nodes() -> list[dict]:
    data = yaml.safe_load(NILE_YAML.read_text())
    nodes = []
    for n in data.get("nodes", []):
        nodes.append({
            "id":  n["id"],
            "lat": float(n["latitude"]),
            "lon": float(n["longitude"]),
        })
    nodes.sort(key=lambda x: x["lat"])
    return nodes


def load_crop_config() -> dict:
    return yaml.safe_load(CROP_YAML.read_text())


def zone_params(node_id: str, cfg: dict) -> dict:
    """Merge zone overrides onto the crop_type template."""
    zone_cfg  = cfg["zones"].get(node_id, {})
    ctype     = zone_cfg.get("crop_type", "highland_cereals")
    template  = cfg["crop_types"].get(ctype, {})
    # Zone overrides take precedence
    merged = {**template, **zone_cfg}
    merged.setdefault("irrigation_efficiency", 0.60)
    merged.setdefault("kc_monthly",
                      [0.90]*12)
    merged.setdefault("food_productivity_kg_m3", 0.75)
    return merged


# ── ERA5 ET₀ → daily ─────────────────────────────────────────────────────────

def load_era5_daily(node_id: str) -> pd.Series:
    """
    Load the cached monthly ERA5 ET₀ CSV for *node_id* and interpolate
    to daily resolution using PCHIP (same method as copernicus_egypt_agriculture.py).
    """
    slug = re.sub(r"\W+", "_", node_id.lower()).strip("_")
    csv  = ERA5_DIR / f"{slug}_{YEAR_FROM}_{YEAR_TO}.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"ERA5 cache not found: {csv}\n"
            "Run copernicus_egypt_agriculture.py first to populate era5_cache/."
        )

    monthly = pd.read_csv(csv, index_col=0, parse_dates=True).squeeze("columns")
    monthly.name = "et0_mm_day"

    # Assign each monthly value to the 15th and PCHIP-interpolate
    mid     = monthly.copy()
    mid.index = pd.DatetimeIndex(
        [pd.Timestamp(t.year, t.month, 15) for t in monthly.index]
    )
    daily_idx = pd.date_range(f"{YEAR_FROM}-01-01", f"{YEAR_TO}-12-31", freq="D")
    epoch     = pd.Timestamp(f"{YEAR_FROM}-01-01")
    x_m = np.array([(t - epoch).days for t in mid.index],   dtype=float)
    x_d = np.array([(t - epoch).days for t in daily_idx], dtype=float)

    interp  = PchipInterpolator(x_m, mid.values, extrapolate=False)
    vals    = interp(x_d)
    s = pd.Series(vals, index=daily_idx).ffill().bfill()
    return np.maximum(s, 0.0).rename("et0_mm_day")


# ── CGLS 5-year mean cropland area ────────────────────────────────────────────

def cgls_mean_area_ha(node_id: str, node_lat: float) -> float:
    """
    Compute the 5-year (2015–2019) mean cropland area (ha) for *node_id*
    from the cached CGLS window arrays.
    """
    annual = {}
    for npy in sorted(CGLS_DIR.glob(f"{node_id}_*_crops_frac.npy")):
        parts = npy.stem.split("_")
        year  = int(parts[1])
        data  = np.load(npy)
        meta  = np.load(npy.with_suffix(".meta.npy"))
        pixel_deg, centre_lat = float(meta[0]), float(meta[1])
        pa_ha = _pixel_area_ha(centre_lat, pixel_deg)
        valid = data[data != 255]
        annual[year] = float((valid.astype(np.float64) / 100.0 * pa_ha).sum())

    if not annual:
        raise FileNotFoundError(
            f"No CGLS cache found for '{node_id}' in {CGLS_DIR}\n"
            "Run nile_agri_area.py first."
        )
    return float(np.mean(list(annual.values())))


def _pixel_area_ha(lat_deg: float, pixel_deg: float) -> float:
    px_rad  = math.radians(pixel_deg)
    area_m2 = (R_EARTH * px_rad) ** 2 * math.cos(math.radians(lat_deg))
    return area_m2 * 1e-4


# ── Kc time series ────────────────────────────────────────────────────────────

def daily_kc(kc_monthly: list[float], daily_index: pd.DatetimeIndex) -> np.ndarray:
    """
    Build a daily Kc series from a 12-element monthly list by assigning
    each month's value to the 15th and PCHIP-interpolating, with circular
    wrap-around so Dec→Jan is smooth.
    """
    kc = np.array(kc_monthly, dtype=float)
    # Extend one month before Jan and one month after Dec for smooth wrap
    months = list(range(1, 13))
    # Representative dates: mid of each month
    rep_dates = [pd.Timestamp(2001, m, 15) for m in months]
    # Wrap: prepend Dec-of-prev-year, append Jan-of-next-year
    ext_dates = (
        [pd.Timestamp(2000, 12, 15)] +
        rep_dates +
        [pd.Timestamp(2002,  1, 15)]
    )
    ext_kc = np.concatenate([[kc[11]], kc, [kc[0]]])

    epoch = pd.Timestamp("2000-12-15")
    x_k   = np.array([(d - epoch).days for d in ext_dates], dtype=float)
    y_k   = ext_kc

    interp = PchipInterpolator(x_k, y_k, extrapolate=True)

    # Map each day to its position within a representative year
    day_of_year = daily_index.dayofyear
    # Use a reference year for interpolation offset (treat every day as 2001)
    ref_epoch   = pd.Timestamp("2000-12-15")
    x_daily = np.array([
        (pd.Timestamp(2001, 1, 1) + pd.Timedelta(days=int(d) - 1) - ref_epoch).days
        for d in day_of_year
    ], dtype=float)

    kc_daily = interp(x_daily)
    return np.clip(kc_daily, 0.15, 1.35)


# ── Main computation ──────────────────────────────────────────────────────────

def compute_zone(node: dict, cfg: dict) -> dict:
    """
    Return a dict with daily Q_gross [m³/s] and metadata for one zone.
    """
    nid    = node["id"]
    params = zone_params(nid, cfg)

    et0     = load_era5_daily(nid)                         # mm/day
    area_ha = cgls_mean_area_ha(nid, node["lat"])          # ha
    eff     = params["irrigation_efficiency"]
    fp      = params["food_productivity_kg_m3"]
    ctype   = params.get("crop_type", "?")
    cdesc   = cfg["crop_types"].get(ctype, {}).get("description", "")

    kc_arr   = daily_kc(params["kc_monthly"], et0.index)
    et_crop  = kc_arr * et0.values                         # mm/day
    v_net    = et_crop * 10.0 * area_ha                    # m³/day  (total crop ET)
    q        = v_net / 86_400.0                            # m³/s

    series = pd.Series(q, index=et0.index, name=nid)
    return {
        "id":          nid,
        "series":      series,
        "area_ha":     area_ha,
        "crop_type":   ctype,
        "crop_desc":   cdesc,
        "eff":         eff,
        "fp_kg_m3":    fp,
    }


# ── Plot ──────────────────────────────────────────────────────────────────────

def make_plot(results: list[dict]) -> None:
    # Sort by average water demand (largest first)
    results_sorted = sorted(results, key=lambda r: r["series"].mean(), reverse=True)
    half           = (len(results_sorted) + 1) // 2
    groups         = [results_sorted[:half], results_sorted[half:]]

    fig, axes = plt.subplots(2, 1, figsize=(18, 12), sharex=True)
    cmap      = plt.get_cmap("tab20", len(results))

    for ax, group in zip(axes, groups):
        for zdata in group:
            s     = zdata["series"]
            nid   = zdata["id"]
            color = cmap(results_sorted.index(zdata))

            # Daily thin line
            ax.plot(s.index, s.values, linewidth=0.35, alpha=0.22, color=color)

            # 365-day rolling mean (bold)
            roll = s.rolling(365, center=True, min_periods=90).mean()
            label = (
                f"{nid.capitalize()}"
                f"  [{zdata['area_ha'] / 1e3:,.0f} k ha"
                f" · {zdata['fp_kg_m3']:.2f} kg food/m³]"
            )
            ax.plot(roll.index, roll.values, linewidth=1.7, color=color, label=label)

        ax.set_ylabel("Total crop water consumption  (m³ s⁻¹)")
        ax.legend(ncol=1, fontsize=7.5, loc="upper left", framealpha=0.9)
        ax.grid(True, alpha=0.25)

        # Shade decades lightly for readability
        for decade in range(1950, 2030, 20):
            ax.axvspan(
                pd.Timestamp(f"{decade}-01-01"),
                pd.Timestamp(f"{decade + 10}-01-01"),
                alpha=0.04, color="grey", linewidth=0
            )

    axes[1].set_xlabel("Year")
    axes[1].xaxis.set_major_locator(mdates.YearLocator(10))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[1].xaxis.set_minor_locator(mdates.YearLocator(5))

    fig.suptitle(
        "Nile Basin Total Agricultural Water Consumption  (m³ s⁻¹)  —  Daily, 1950–2026\n"
        "ET_crop = Kc × ERA5-Land ET₀ × CGLS-LC100 mean cropland area (2015–2019)\n"
        "Includes all water consumed by crops (rainfall + irrigation combined)\n"
        "Legend: [CGLS mean area · food productivity (kg food / m³ consumed)]",
        fontsize=10,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_PNG, dpi=150)
    print(f"Saved {OUT_PNG}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    nodes = load_nodes()
    cfg   = load_crop_config()

    print(f"Computing daily water demand for {len(nodes)} zones, {YEAR_FROM}–{YEAR_TO}")
    print(f"  Areas from CGLS-LC100 v3 (2015–2019 mean)")
    print(f"  ET₀ from ERA5-Land (cached in {ERA5_DIR.name}/)")
    print()

    results    = []
    daily_dfs  = {}

    for node in nodes:
        nid = node["id"]
        try:
            zdata = compute_zone(node, cfg)
        except FileNotFoundError as exc:
            print(f"  SKIP {nid}: {exc}")
            continue

        params = zone_params(nid, cfg)
        print(
            f"  {nid:12s}  area={zdata['area_ha']:>10,.0f} ha"
            f"  crop={params.get('crop_type','?')}"
            f"  fp={params['food_productivity_kg_m3']:.2f} kg/m³"
            f"  peak={zdata['series'].max():.1f} m³/s"
            f"  mean={zdata['series'].mean():.1f} m³/s"
        )
        results.append(zdata)
        daily_dfs[nid] = zdata["series"]

    # Export CSV — date + per-zone daily water usage in m³/day + total
    df = pd.DataFrame({nid: zdata["series"] * 86_400.0 for nid, zdata in
                       ((r["id"], r) for r in results)})
    df.index.name = "date"
    df["total_m3"] = df.sum(axis=1)
    # Write the two-column summary the user asked for (date + total m³/day)
    df[["total_m3"]].rename(columns={"total_m3": "water_usage_m3"}).to_csv(
        OUT_CSV, float_format="%.0f"
    )
    print(f"\nSaved {OUT_CSV}  ({len(df)} rows, date + water_usage_m3 [m³/day])")

    # Plot
    make_plot(results)


if __name__ == "__main__":
    main()
