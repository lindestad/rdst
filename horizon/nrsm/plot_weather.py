"""
Baseline weather-year scenario plots.

Runs all 60 five-year weather-year scenarios with original reservoir
initial levels at Full, Half, None and Random production actions.

Run with:
    python3 plot_weather.py
"""

from pathlib import Path

import matplotlib.pyplot as plt

from plot_weather_lib import load_scenarios, run_all_plots

DIRECTORY = Path(__file__).parent / "scenarios" / "nile-mvp" / "weather_years"
TAG       = "Baseline — original initial levels"


def main() -> None:
    print(f"Loading scenarios: {TAG}")
    print("(60 scenarios x 12 action levels = 720 runs)")
    results = load_scenarios(DIRECTORY)
    print("Plotting...")
    run_all_plots(results, TAG)
    plt.show()


if __name__ == "__main__":
    main()
