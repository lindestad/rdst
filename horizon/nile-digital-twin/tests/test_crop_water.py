import numpy as np

from simengine.crop_water import monthly_water_requirement_mm


def test_peak_in_summer_northern_hemisphere():
    vals = [monthly_water_requirement_mm(m) for m in range(1, 13)]
    assert max(vals) == vals[6] or max(vals) == vals[5] or max(vals) == vals[7]


def test_positive_everywhere():
    for m in range(1, 13):
        assert monthly_water_requirement_mm(m) > 0
