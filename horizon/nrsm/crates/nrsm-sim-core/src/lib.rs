mod error;
mod model;
mod sim;

pub use error::SimulationError;
pub use model::{
    ConnectionConfig, DrinkWaterModule, EnergyModule, EngineTimeStep, EvaporationModule,
    FoodProductionModule, ModuleSeries, ModuleSourceType, NodeActions, NodeConfig, NodeModules,
    NodeResult, PeriodResult, ReportingFrequency, ReservoirConfig, Scenario, SimulationResult,
    SimulationSettings, SimulationSummary,
};
pub use sim::{PreparedScenario, simulate, simulate_with_actions};
