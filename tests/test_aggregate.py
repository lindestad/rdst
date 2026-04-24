from dataloader.aggregate import crop_bbox, monthly_forcings_from_era5


def test_crop_bbox_keeps_only_interior_points(era5_mini_ds):
    cropped = crop_bbox(era5_mini_ds, lat_min=14.7, lat_max=15.3,
                        lon_min=32.7, lon_max=33.3)
    assert set(cropped.latitude.values.tolist()) == {15.0}
    assert set(cropped.longitude.values.tolist()) == {33.0}


def test_monthly_forcings_has_spec_columns(era5_mini_ds):
    df = monthly_forcings_from_era5(
        era5_mini_ds,
        lat_min=14.0, lat_max=16.0, lon_min=32.0, lon_max=34.0,
    )
    assert list(df.columns) == [
        "month", "precip_mm", "temp_c", "radiation_mj_m2",
        "wind_ms", "dewpoint_c", "pet_mm", "runoff_mm", "historical_discharge_m3s",
    ]
    assert len(df) == 2
    assert 20 < df["temp_c"].mean() < 30
    assert 0 < df["precip_mm"].mean() < 200
    assert df["historical_discharge_m3s"].isna().all()
