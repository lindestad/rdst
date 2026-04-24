import numpy as np

from dataloader.penman import pet_mm_monthly


def test_pet_at_aswan_july_is_in_sane_range():
    # Aswan July climatology (rough): T=33°C, Td=5°C (very dry),
    # radiation ~28 MJ/m²/day, wind ~3 m/s. Expect ~8–14 mm/day → 250–430 mm/month.
    pet = pet_mm_monthly(
        temp_c=33.0, dewpoint_c=5.0, radiation_mj_m2_day=28.0,
        wind_ms=3.0, days_in_month=31,
    )
    assert 250 <= pet <= 430, f"unexpected PET {pet:.1f} mm/month"


def test_pet_at_cool_humid_is_small():
    pet = pet_mm_monthly(
        temp_c=10.0, dewpoint_c=9.0, radiation_mj_m2_day=6.0,
        wind_ms=1.5, days_in_month=30,
    )
    assert 10 <= pet <= 80


def test_pet_vectorizes_over_arrays():
    temp = np.array([10.0, 20.0, 33.0])
    dew = np.array([9.0, 10.0, 5.0])
    rad = np.array([6.0, 18.0, 28.0])
    wind = np.array([1.5, 2.0, 3.0])
    days = np.array([31, 28, 31])
    pet = pet_mm_monthly(temp, dew, rad, wind, days)
    assert pet.shape == (3,)
    assert np.all(pet > 0)
    assert pet[2] > pet[0]
