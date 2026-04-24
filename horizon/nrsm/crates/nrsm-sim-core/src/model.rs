use serde::{Deserialize, Serialize};

pub const SUPPORTED_SCHEMA_VERSION: &str = "0.1.0";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Scenario {
    #[serde(default = "default_schema_version")]
    pub schema_version: String,
    pub metadata: ScenarioMetadata,
    pub simulation: SimulationConfig,
    pub network: NetworkConfig,
}

fn default_schema_version() -> String {
    SUPPORTED_SCHEMA_VERSION.to_string()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScenarioMetadata {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SimulationConfig {
    pub horizon_days: usize,
    pub reporting: ReportingFrequency,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReportingFrequency {
    Daily,
    Monthly30Day,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub nodes: Vec<NodeConfig>,
    pub edges: Vec<EdgeConfig>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NodeConfig {
    pub id: String,
    pub name: String,
    pub kind: NodeKind,
    pub local_inflow: TimeSeries,
    #[serde(default)]
    pub reservoir: Option<ReservoirConfig>,
    #[serde(default)]
    pub drinking_water: Option<DrinkingWaterDemand>,
    #[serde(default)]
    pub irrigation: Option<IrrigationDemand>,
    #[serde(default)]
    pub hydropower: Option<HydropowerPlant>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum NodeKind {
    River,
    Reservoir,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EdgeConfig {
    pub id: String,
    pub from: String,
    pub to: String,
    pub flow_share: f64,
    pub loss_fraction: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReservoirConfig {
    pub capacity: f64,
    pub min_storage: f64,
    pub initial_storage: f64,
    pub target_release: TimeSeries,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DrinkingWaterDemand {
    #[serde(default)]
    pub minimum_daily_delivery: Option<TimeSeries>,
    pub target_daily_delivery: TimeSeries,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IrrigationDemand {
    #[serde(default)]
    pub minimum_daily_delivery: Option<TimeSeries>,
    pub target_daily_delivery: TimeSeries,
    pub food_per_unit_water: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HydropowerPlant {
    #[serde(default)]
    pub minimum_daily_energy: Option<TimeSeries>,
    #[serde(default)]
    pub target_daily_energy: Option<TimeSeries>,
    pub max_turbine_flow: TimeSeries,
    pub energy_per_unit_water: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum TimeSeries {
    Constant { value: f64 },
    Daily { values: Vec<f64> },
    Monthly30Day { values: Vec<f64> },
}

impl TimeSeries {
    pub fn value_at(&self, day: usize) -> f64 {
        match self {
            Self::Constant { value } => *value,
            Self::Daily { values } => values[day % values.len()],
            Self::Monthly30Day { values } => values[(day / 30) % values.len()],
        }
    }

    pub fn validate(&self, label: &str) -> Result<(), String> {
        match self {
            Self::Constant { .. } => Ok(()),
            Self::Daily { values } | Self::Monthly30Day { values } => {
                if values.is_empty() {
                    return Err(format!("{label} cannot be empty"));
                }

                Ok(())
            }
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct SimulationResult {
    pub schema_version: String,
    pub metadata: ScenarioMetadata,
    pub engine_time_step: EngineTimeStep,
    pub reporting: ReportingFrequency,
    pub summary: SimulationSummary,
    pub periods: Vec<PeriodResult>,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EngineTimeStep {
    Daily,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct SimulationSummary {
    pub total_incoming_flow: f64,
    pub total_local_inflow: f64,
    pub total_edge_loss: f64,
    pub total_drinking_water_delivered: f64,
    pub total_irrigation_water_delivered: f64,
    pub total_food_produced: f64,
    pub total_energy_generated: f64,
    pub total_basin_exit_flow: f64,
    pub total_drinking_shortfall_to_minimum: f64,
    pub total_irrigation_shortfall_to_minimum: f64,
    pub total_energy_shortfall_to_minimum: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct PeriodResult {
    pub period_index: usize,
    pub start_day: usize,
    pub end_day_exclusive: usize,
    pub total_incoming_flow: f64,
    pub total_local_inflow: f64,
    pub total_edge_loss: f64,
    pub total_basin_exit_flow: f64,
    pub node_results: Vec<NodeResult>,
    pub edge_results: Vec<EdgeResult>,
}

#[derive(Clone, Debug, Serialize)]
pub struct NodeResult {
    pub node_id: String,
    pub node_name: String,
    pub node_kind: NodeKind,
    pub total_incoming_flow: f64,
    pub total_local_inflow: f64,
    pub starting_storage: f64,
    pub ending_storage: f64,
    pub total_available_water: f64,
    pub total_downstream_outflow: f64,
    pub total_basin_exit_outflow: f64,
    pub drinking_water: Option<DeliveryResult>,
    pub irrigation: Option<IrrigationResult>,
    pub hydropower: Option<HydropowerResult>,
}

#[derive(Clone, Debug, Serialize)]
pub struct EdgeResult {
    pub edge_id: String,
    pub from_node: String,
    pub to_node: String,
    pub total_routed_flow: f64,
    pub total_lost_flow: f64,
    pub total_received_flow: f64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct DeliveryResult {
    pub actual_delivery: f64,
    pub total_target: f64,
    pub total_minimum_target: f64,
    pub shortfall_to_target: f64,
    pub shortfall_to_minimum: f64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct IrrigationResult {
    pub water: DeliveryResult,
    pub food_produced: f64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct HydropowerResult {
    pub turbine_flow: f64,
    pub energy_generated: f64,
    pub total_target_energy: f64,
    pub total_minimum_energy: f64,
    pub shortfall_to_target: f64,
    pub shortfall_to_minimum: f64,
}
