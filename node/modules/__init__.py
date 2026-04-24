"""modules package for the water resource simulator."""
from .catchment_inflow import CatchmentInflow, ConstantInflow, CSVInflow, TimeSeriesInflow
from .drink_water import CSVDrinkWater, DrinkWaterDemand, TimeSeriesDrinkWater
from .food_production import CSVFoodProduction, FoodProduction, TimeSeriesFoodProduction
from .energy_price import CSVEnergyPrice, EnergyPrice, TimeSeriesEnergyPrice

__all__ = [
    # catchment inflow
    "CatchmentInflow",
    "ConstantInflow",
    "TimeSeriesInflow",
    "CSVInflow",
    # drink water
    "DrinkWaterDemand",
    "TimeSeriesDrinkWater",
    "CSVDrinkWater",
    # food production
    "FoodProduction",
    "TimeSeriesFoodProduction",
    "CSVFoodProduction",
    # energy price
    "EnergyPrice",
    "TimeSeriesEnergyPrice",
    "CSVEnergyPrice",
]
