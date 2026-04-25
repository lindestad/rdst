use std::{
    fs,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use crate::error::SimulationError;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Scenario {
    #[serde(default)]
    pub settings: SimulationSettings,
    pub nodes: Vec<NodeConfig>,
}

impl Scenario {
    pub fn load_module_csvs(&mut self, base_dir: impl AsRef<Path>) -> Result<(), SimulationError> {
        let base_dir = base_dir.as_ref();

        for node in &mut self.nodes {
            node.catchment_inflow
                .load_csv(base_dir, &format!("node `{}` catchment_inflow", node.id))?;
            node.modules
                .evaporation
                .rate
                .load_csv(base_dir, &format!("node `{}` evaporation", node.id))?;
            node.modules
                .drink_water
                .daily_demand
                .load_csv(base_dir, &format!("node `{}` drink_water", node.id))?;
            node.modules
                .food_production
                .max_food_units
                .load_csv(base_dir, &format!("node `{}` food_production", node.id))?;
            node.modules
                .energy
                .price_per_unit
                .load_csv(base_dir, &format!("node `{}` energy", node.id))?;
            if let Some(actions) = &mut node.actions {
                actions.production_level.load_csv(
                    base_dir,
                    &format!("node `{}` actions.production_level", node.id),
                )?;
            }
        }

        Ok(())
    }

    pub fn horizon_days(&self) -> usize {
        self.settings
            .horizon_days
            .or_else(|| self.inferred_csv_horizon_days())
            .unwrap_or(1)
    }

    fn inferred_csv_horizon_days(&self) -> Option<usize> {
        self.nodes
            .iter()
            .flat_map(|node| {
                [
                    node.catchment_inflow.loaded_len(),
                    node.modules.evaporation.rate.loaded_len(),
                    node.modules.drink_water.daily_demand.loaded_len(),
                    node.modules.food_production.max_food_units.loaded_len(),
                    node.modules.energy.price_per_unit.loaded_len(),
                    node.actions
                        .as_ref()
                        .and_then(|actions| actions.production_level.loaded_len()),
                ]
            })
            .flatten()
            .min()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SimulationSettings {
    #[serde(default = "default_timestep_days")]
    pub timestep_days: f64,
    #[serde(default)]
    pub horizon_days: Option<usize>,
    #[serde(default)]
    pub reporting: ReportingFrequency,
    #[serde(default = "default_production_level_fraction")]
    pub production_level_fraction: f64,
}

impl Default for SimulationSettings {
    fn default() -> Self {
        Self {
            timestep_days: default_timestep_days(),
            horizon_days: None,
            reporting: ReportingFrequency::default(),
            production_level_fraction: default_production_level_fraction(),
        }
    }
}

fn default_timestep_days() -> f64 {
    1.0
}

fn default_production_level_fraction() -> f64 {
    1.0
}

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ReportingFrequency {
    #[default]
    Daily,
    Monthly30Day,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NodeConfig {
    pub id: String,
    pub reservoir: ReservoirConfig,
    pub max_production: f64,
    pub catchment_inflow: ModuleSeries,
    #[serde(default)]
    pub connections: Vec<ConnectionConfig>,
    #[serde(default)]
    pub modules: NodeModules,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actions: Option<NodeActions>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReservoirConfig {
    pub initial_level: f64,
    pub max_capacity: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ConnectionConfig {
    pub node_id: String,
    pub fraction: f64,
    #[serde(default)]
    pub delay: usize,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct NodeModules {
    #[serde(default)]
    pub evaporation: EvaporationModule,
    #[serde(default)]
    pub drink_water: DrinkWaterModule,
    #[serde(default)]
    pub food_production: FoodProductionModule,
    #[serde(default)]
    pub energy: EnergyModule,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NodeActions {
    #[serde(default = "default_production_level_series")]
    pub production_level: ModuleSeries,
}

impl Default for NodeActions {
    fn default() -> Self {
        Self {
            production_level: ModuleSeries::constant(1.0),
        }
    }
}

fn default_production_level_series() -> ModuleSeries {
    ModuleSeries::constant(1.0)
}

#[derive(Clone, Debug, Serialize)]
pub struct EvaporationModule {
    #[serde(flatten)]
    pub rate: ModuleSeries,
}

impl Default for EvaporationModule {
    fn default() -> Self {
        Self {
            rate: ModuleSeries::constant(0.0),
        }
    }
}

impl<'de> Deserialize<'de> for EvaporationModule {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        #[derive(Deserialize)]
        #[serde(untagged)]
        enum Input {
            Scalar(f64),
            Structured(ModuleSeries),
        }

        match Input::deserialize(deserializer)? {
            Input::Scalar(value) => Ok(Self {
                rate: ModuleSeries::constant(value),
            }),
            Input::Structured(rate) => Ok(Self { rate }),
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct DrinkWaterModule {
    #[serde(flatten)]
    pub daily_demand: ModuleSeries,
}

impl Default for DrinkWaterModule {
    fn default() -> Self {
        Self {
            daily_demand: ModuleSeries::constant(0.0),
        }
    }
}

impl<'de> Deserialize<'de> for DrinkWaterModule {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        #[derive(Deserialize)]
        #[serde(untagged)]
        enum Input {
            Scalar(f64),
            Structured(ModuleSeries),
        }

        match Input::deserialize(deserializer)? {
            Input::Scalar(value) => Ok(Self {
                daily_demand: ModuleSeries::constant(value),
            }),
            Input::Structured(daily_demand) => Ok(Self { daily_demand }),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FoodProductionModule {
    #[serde(default = "default_water_coefficient")]
    pub water_coefficient: f64,
    #[serde(flatten)]
    pub max_food_units: ModuleSeries,
}

impl Default for FoodProductionModule {
    fn default() -> Self {
        Self {
            water_coefficient: default_water_coefficient(),
            max_food_units: ModuleSeries::constant(0.0),
        }
    }
}

fn default_water_coefficient() -> f64 {
    1.0
}

impl FoodProductionModule {
    pub fn water_demand(&self, day: usize, dt_days: f64) -> f64 {
        if self.water_coefficient <= 0.0 {
            return 0.0;
        }

        (self.max_food_units.value_at(day) * dt_days).max(0.0) * self.water_coefficient
    }

    pub fn produce(&self, available_water: f64, day: usize, dt_days: f64) -> (f64, f64) {
        if self.water_coefficient <= 0.0 {
            return (0.0, 0.0);
        }

        let max_food_units = (self.max_food_units.value_at(day) * dt_days).max(0.0);
        let food_produced = (available_water / self.water_coefficient).min(max_food_units);
        let water_consumed = food_produced * self.water_coefficient;

        (food_produced, water_consumed)
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct EnergyModule {
    #[serde(flatten)]
    pub price_per_unit: ModuleSeries,
}

impl Default for EnergyModule {
    fn default() -> Self {
        Self {
            price_per_unit: ModuleSeries::constant(0.0),
        }
    }
}

impl<'de> Deserialize<'de> for EnergyModule {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        #[derive(Deserialize)]
        #[serde(untagged)]
        enum Input {
            Scalar(f64),
            Structured(ModuleSeries),
        }

        match Input::deserialize(deserializer)? {
            Input::Scalar(value) => Ok(Self {
                price_per_unit: ModuleSeries::constant(value),
            }),
            Input::Structured(price_per_unit) => Ok(Self { price_per_unit }),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModuleSeries {
    #[serde(rename = "type", default)]
    pub source_type: Option<ModuleSourceType>,
    #[serde(
        default,
        alias = "rate",
        alias = "daily_demand",
        alias = "max_food_units",
        alias = "price_per_unit",
        alias = "production_level"
    )]
    pub value: Option<f64>,
    #[serde(default)]
    pub filepath: Option<PathBuf>,
    #[serde(default = "default_scenario_column")]
    pub column: String,
    #[serde(skip)]
    pub values: Vec<f64>,
}

impl Default for ModuleSeries {
    fn default() -> Self {
        Self::constant(0.0)
    }
}

impl ModuleSeries {
    pub fn constant(value: f64) -> Self {
        Self {
            source_type: Some(ModuleSourceType::Constant),
            value: Some(value),
            filepath: None,
            column: default_scenario_column(),
            values: Vec::new(),
        }
    }

    pub fn value_at(&self, day: usize) -> f64 {
        if self.is_csv() {
            return self.values[day % self.values.len()];
        }

        self.value.unwrap_or_default()
    }

    pub fn validate(&self, label: &str) -> Result<(), String> {
        if self.is_csv() {
            if self.values.is_empty() {
                return Err(format!("{label} CSV source has no loaded values"));
            }
            return Ok(());
        }

        if self.value.is_none() {
            return Err(format!("{label} constant source is missing a value"));
        }

        Ok(())
    }

    pub fn loaded_len(&self) -> Option<usize> {
        self.is_csv().then_some(self.values.len())
    }

    fn load_csv(&mut self, base_dir: &Path, label: &str) -> Result<(), SimulationError> {
        if !self.is_csv() {
            return Ok(());
        }

        let Some(filepath) = &self.filepath else {
            return Err(SimulationError::Validation(format!(
                "{label} CSV source is missing filepath"
            )));
        };
        let path = if filepath.is_absolute() {
            filepath.clone()
        } else {
            base_dir.join(filepath)
        };
        let content = fs::read_to_string(&path).map_err(|error| {
            SimulationError::Validation(format!(
                "{label} CSV source `{}` could not be read: {error}",
                path.display()
            ))
        })?;
        self.values = parse_csv_column(&content, &self.column, label)?;

        Ok(())
    }

    fn is_csv(&self) -> bool {
        matches!(self.source_type, Some(ModuleSourceType::Csv)) || self.filepath.is_some()
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ModuleSourceType {
    Constant,
    Csv,
}

fn default_scenario_column() -> String {
    "scenario_1".to_string()
}

fn parse_csv_column(content: &str, column: &str, label: &str) -> Result<Vec<f64>, SimulationError> {
    let mut lines = content.lines().filter(|line| !line.trim().is_empty());
    let Some(header) = lines.next() else {
        return Err(SimulationError::Validation(format!(
            "{label} CSV source is empty"
        )));
    };
    let headers = split_csv_line(header);
    let Some(column_index) = headers.iter().position(|header| header == column) else {
        return Err(SimulationError::Validation(format!(
            "{label} CSV source is missing column `{column}`"
        )));
    };

    let mut values = Vec::new();
    for (line_index, line) in lines.enumerate() {
        let fields = split_csv_line(line);
        let Some(raw_value) = fields.get(column_index) else {
            return Err(SimulationError::Validation(format!(
                "{label} CSV row {} is missing column `{column}`",
                line_index + 2
            )));
        };
        let value = raw_value.parse::<f64>().map_err(|error| {
            SimulationError::Validation(format!(
                "{label} CSV row {} has invalid `{column}` value `{raw_value}`: {error}",
                line_index + 2
            ))
        })?;
        values.push(value);
    }

    if values.is_empty() {
        return Err(SimulationError::Validation(format!(
            "{label} CSV source has no data rows"
        )));
    }

    Ok(values)
}

fn split_csv_line(line: &str) -> Vec<String> {
    line.split(',')
        .map(|field| field.trim().trim_matches('"').to_string())
        .collect()
}

#[derive(Clone, Debug, Serialize)]
pub struct SimulationResult {
    pub engine_time_step: EngineTimeStep,
    pub timestep_days: f64,
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
    pub total_inflow: f64,
    pub total_evaporation: f64,
    pub total_drink_water_met: f64,
    pub total_unmet_drink_water: f64,
    pub total_food_water_demand: f64,
    pub total_food_water_met: f64,
    pub total_unmet_food_water: f64,
    pub total_food_produced: f64,
    pub total_production_release: f64,
    pub total_energy_value: f64,
    pub total_spill: f64,
    pub total_downstream_release: f64,
    pub total_routing_loss: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct PeriodResult {
    pub period_index: usize,
    pub start_day: usize,
    pub end_day_exclusive: usize,
    pub node_results: Vec<NodeResult>,
}

#[derive(Clone, Debug, Serialize)]
pub struct NodeResult {
    pub node_id: String,
    pub action: f64,
    pub reservoir_level: f64,
    pub production_release: f64,
    pub energy_value: f64,
    pub evaporation: f64,
    pub food_water_demand: f64,
    pub food_water_met: f64,
    pub unmet_food_water: f64,
    pub food_produced: f64,
    pub drink_water_met: f64,
    pub unmet_drink_water: f64,
    pub spill: f64,
    pub downstream_release: f64,
    pub total_inflow: f64,
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::Scenario;

    #[test]
    fn loads_selected_csv_scenario_columns_and_infers_shortest_horizon() {
        let unique = format!(
            "nrsm-module-series-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        fs::create_dir_all(&dir).expect("temporary directory should be created");
        fs::write(
            dir.join("inflow.csv"),
            "date,scenario_1,scenario_2\n2020-01-01,1,10\n2020-01-02,2,20\n2020-01-03,3,30\n",
        )
        .expect("inflow csv should be written");
        fs::write(
            dir.join("food.csv"),
            "date,scenario_1,scenario_2\n2020-01-01,4,40\n2020-01-02,5,50\n",
        )
        .expect("food csv should be written");
        fs::write(
            dir.join("actions.csv"),
            "date,scenario_1,scenario_2\n2020-01-01,0.1,0.6\n2020-01-02,0.2,0.7\n2020-01-03,0.3,0.8\n",
        )
        .expect("actions csv should be written");

        let mut scenario: Scenario = serde_yaml::from_str(
            r#"
nodes:
  - id: test_node
    reservoir:
      initial_level: 0.0
      max_capacity: 1000.0
    max_production: 100.0
    catchment_inflow:
      type: csv
      filepath: inflow.csv
      column: scenario_2
    modules:
      food_production:
        type: csv
        filepath: food.csv
        column: scenario_2
        water_coefficient: 2.0
    actions:
      production_level:
        type: csv
        filepath: actions.csv
        column: scenario_2
"#,
        )
        .expect("scenario yaml should parse");

        scenario
            .load_module_csvs(&dir)
            .expect("module CSVs should load");

        let node = &scenario.nodes[0];
        assert_eq!(node.catchment_inflow.value_at(0), 10.0);
        assert_eq!(node.catchment_inflow.value_at(2), 30.0);
        assert_eq!(
            node.modules.food_production.max_food_units.value_at(1),
            50.0
        );
        assert_eq!(
            node.actions
                .as_ref()
                .expect("actions should exist")
                .production_level
                .value_at(1),
            0.7
        );
        assert_eq!(scenario.horizon_days(), 2);

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    #[test]
    fn reports_missing_csv_scenario_column() {
        let unique = format!(
            "nrsm-module-series-missing-column-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        fs::create_dir_all(&dir).expect("temporary directory should be created");
        fs::write(dir.join("inflow.csv"), "date,scenario_1\n2020-01-01,1\n")
            .expect("inflow csv should be written");

        let mut scenario: Scenario = serde_yaml::from_str(
            r#"
nodes:
  - id: test_node
    reservoir:
      initial_level: 0.0
      max_capacity: 1000.0
    max_production: 100.0
    catchment_inflow:
      type: csv
      filepath: inflow.csv
      column: scenario_2
"#,
        )
        .expect("scenario yaml should parse");

        let error = scenario
            .load_module_csvs(&dir)
            .expect_err("missing scenario column should fail");

        assert!(error.to_string().contains("missing column `scenario_2`"));

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    #[test]
    fn accepts_scalar_shorthand_for_simple_modules() {
        let scenario: Scenario = serde_yaml::from_str(
            r#"
nodes:
  - id: test_node
    reservoir:
      initial_level: 0.0
      max_capacity: 1000.0
    max_production: 100.0
    catchment_inflow:
      rate: 10.0
    modules:
      evaporation: 1.0
      drink_water: 2.0
      energy: 0.5
"#,
        )
        .expect("scenario yaml should parse");

        let modules = &scenario.nodes[0].modules;
        assert_eq!(modules.evaporation.rate.value_at(0), 1.0);
        assert_eq!(modules.drink_water.daily_demand.value_at(0), 2.0);
        assert_eq!(modules.energy.price_per_unit.value_at(0), 0.5);
    }
}
