import pandas as pd
import xarray as xr

from dataloader.era5 import _iter_month_requests, _merge_variable_chunks


def test_iter_month_requests_splits_range_by_calendar_month():
    chunks = _iter_month_requests("2005-01-15", "2005-03-02")

    assert [(year, month) for year, month, _ in chunks] == [
        ("2005", "01"),
        ("2005", "02"),
        ("2005", "03"),
    ]
    assert chunks[0][2][0] == "01"
    assert chunks[0][2][-1] == "31"
    assert chunks[1][2][-1] == "28"
    assert chunks[2][2][-1] == "31"


def test_iter_month_requests_handles_single_month():
    chunks = _iter_month_requests("2024-02-01", "2024-02-29")

    assert len(chunks) == 1
    assert chunks[0][0] == "2024"
    assert chunks[0][1] == "02"
    assert chunks[0][2][-1] == "29"


def test_merge_variable_chunks_normalizes_valid_time(tmp_path):
    times = pd.date_range("2005-01-01", periods=2, freq="D")
    lat = [10.0]
    lon = [30.0]
    tp = xr.Dataset(
        {"tp": (("valid_time", "latitude", "longitude"), [[[1.0]], [[2.0]]])},
        coords={"valid_time": times, "latitude": lat, "longitude": lon},
    )
    t2m = xr.Dataset(
        {"t2m": (("valid_time", "latitude", "longitude"), [[[295.0]], [[296.0]]])},
        coords={"valid_time": times, "latitude": lat, "longitude": lon},
    )
    tp_path = tmp_path / "tp.nc"
    t2m_path = tmp_path / "t2m.nc"
    out_path = tmp_path / "merged.nc"
    tp.to_netcdf(tp_path)
    t2m.to_netcdf(t2m_path)

    _merge_variable_chunks([tp_path, t2m_path], out_path)

    merged = xr.open_dataset(out_path)
    try:
        assert set(merged.data_vars) == {"tp", "t2m"}
        assert "time" in merged.dims
        assert "valid_time" not in merged.dims
    finally:
        merged.close()
