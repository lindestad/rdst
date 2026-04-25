use std::collections::{HashMap, VecDeque};

use crate::{
    error::SimulationError,
    model::{
        EngineTimeStep, NodeConfig, NodeResult, PeriodResult, ReportingFrequency, Scenario,
        SimulationResult, SimulationSummary,
    },
};

const FLOAT_TOLERANCE: f64 = 1e-9;

pub fn simulate(scenario: &Scenario) -> Result<SimulationResult, SimulationError> {
    PreparedScenario::try_new(scenario.clone())?.simulate()
}

#[derive(Clone, Debug)]
pub struct PreparedScenario {
    scenario: Scenario,
    compiled: CompiledNetwork,
    horizon_days: usize,
    node_ids: Vec<String>,
}

impl PreparedScenario {
    pub fn try_new(scenario: Scenario) -> Result<Self, SimulationError> {
        validate_scenario(&scenario)?;
        let compiled = CompiledNetwork::build(&scenario.nodes)?;
        let horizon_days = scenario.horizon_days();
        let node_ids = scenario
            .nodes
            .iter()
            .map(|node| node.id.clone())
            .collect::<Vec<_>>();

        Ok(Self {
            scenario,
            compiled,
            horizon_days,
            node_ids,
        })
    }

    pub fn simulate(&self) -> Result<SimulationResult, SimulationError> {
        self.simulate_with_optional_actions(None)
    }

    pub fn simulate_summary(&self) -> Result<SimulationSummary, SimulationError> {
        Ok(simulate_daily_summary(&self.scenario, &self.compiled, None))
    }

    pub fn simulate_with_actions(
        &self,
        actions: &[f64],
    ) -> Result<SimulationResult, SimulationError> {
        self.validate_action_matrix(actions)?;
        self.simulate_with_optional_actions(Some(actions))
    }

    pub fn simulate_summary_with_actions(
        &self,
        actions: &[f64],
    ) -> Result<SimulationSummary, SimulationError> {
        self.validate_action_matrix(actions)?;
        Ok(simulate_daily_summary(
            &self.scenario,
            &self.compiled,
            Some(actions),
        ))
    }

    pub fn node_ids(&self) -> &[String] {
        &self.node_ids
    }

    pub fn node_count(&self) -> usize {
        self.node_ids.len()
    }

    pub fn horizon_days(&self) -> usize {
        self.horizon_days
    }

    pub fn expected_action_len(&self) -> usize {
        self.horizon_days * self.node_count()
    }

    fn simulate_with_optional_actions(
        &self,
        action_matrix: Option<&[f64]>,
    ) -> Result<SimulationResult, SimulationError> {
        let daily_periods = simulate_daily_periods(&self.scenario, &self.compiled, action_matrix);
        let periods = aggregate_periods(&daily_periods, self.scenario.settings.reporting);
        let summary = summarize(&periods);

        Ok(SimulationResult {
            engine_time_step: EngineTimeStep::Daily,
            timestep_days: self.scenario.settings.timestep_days,
            reporting: self.scenario.settings.reporting,
            summary,
            periods,
        })
    }

    fn validate_action_matrix(&self, actions: &[f64]) -> Result<(), SimulationError> {
        let expected = self.expected_action_len();
        if actions.len() != expected {
            return Err(SimulationError::Validation(format!(
                "action matrix length must be horizon_days * node_count = {expected}, found {}",
                actions.len()
            )));
        }
        Ok(())
    }
}

pub fn simulate_with_actions(
    scenario: &Scenario,
    actions: &[f64],
) -> Result<SimulationResult, SimulationError> {
    PreparedScenario::try_new(scenario.clone())?.simulate_with_actions(actions)
}

fn action_at(
    scenario: &Scenario,
    node: &NodeConfig,
    node_index: usize,
    day: usize,
    node_count: usize,
    action_matrix: Option<&[f64]>,
) -> f64 {
    let action = action_matrix
        .map(|actions| actions[day * node_count + node_index])
        .or_else(|| {
            node.actions
                .as_ref()
                .map(|actions| actions.production_level.value_at(day))
        })
        .unwrap_or(scenario.settings.production_level_fraction);

    action.clamp(0.0, 1.0)
}

fn simulate_daily_periods(
    scenario: &Scenario,
    compiled: &CompiledNetwork,
    action_matrix: Option<&[f64]>,
) -> Vec<PeriodResult> {
    let node_count = scenario.nodes.len();
    let horizon_days = scenario.horizon_days();
    let max_delay = compiled.max_delay;
    let dt_days = scenario.settings.timestep_days;
    let mut reservoir_levels = scenario
        .nodes
        .iter()
        .map(|node| node.reservoir.initial_level)
        .collect::<Vec<_>>();
    let mut scheduled_arrivals = vec![vec![0.0; node_count]; horizon_days + max_delay + 1];
    let mut periods = Vec::with_capacity(horizon_days);

    for day in 0..horizon_days {
        let mut arrivals = scheduled_arrivals[day].clone();
        let mut node_results = Vec::with_capacity(node_count);

        for &node_index in &compiled.topological_order {
            let node = &scenario.nodes[node_index];
            let upstream_inflow = arrivals[node_index];
            let catchment_inflow = node.catchment_inflow.value_at(day) * dt_days;
            let total_inflow = catchment_inflow + upstream_inflow;
            let mut available = reservoir_levels[node_index] + total_inflow;

            let evaporation = (node.modules.evaporation.rate.value_at(day) * dt_days)
                .max(0.0)
                .min(available);
            available -= evaporation;

            let drink_water_demand =
                (node.modules.drink_water.daily_demand.value_at(day) * dt_days).max(0.0);
            let drink_water_met = drink_water_demand.min(available);
            let unmet_drink_water = drink_water_demand - drink_water_met;
            available -= drink_water_met;

            let food_water_demand = node.modules.food_production.water_demand(day, dt_days);
            let (food_produced, food_water_met) = node
                .modules
                .food_production
                .produce(available, day, dt_days);
            let unmet_food_water = food_water_demand - food_water_met;
            available -= food_water_met;

            let action_fraction =
                action_at(scenario, node, node_index, day, node_count, action_matrix);
            let max_release = (node.max_production * dt_days * action_fraction).max(0.0);
            let production_release = max_release.min(available);
            available -= production_release;

            let spill = (available - node.reservoir.max_capacity).max(0.0);
            let reservoir_level = available.clamp(0.0, node.reservoir.max_capacity);
            reservoir_levels[node_index] = reservoir_level;

            let release_for_routing = production_release + spill;
            let mut downstream_release = 0.0;

            for &connection_index in &compiled.outgoing_connections[node_index] {
                let connection = &compiled.connections[connection_index];
                let routed = release_for_routing * connection.fraction;
                downstream_release += routed;

                if connection.delay == 0 {
                    arrivals[connection.to_index] += routed;
                } else {
                    scheduled_arrivals[day + connection.delay][connection.to_index] += routed;
                }
            }

            let energy_value =
                production_release * node.modules.energy.price_per_unit.value_at(day);

            node_results.push(NodeResult {
                node_id: node.id.clone(),
                action: action_fraction,
                reservoir_level,
                production_release,
                energy_value,
                evaporation,
                food_water_demand,
                food_water_met,
                unmet_food_water,
                food_produced,
                drink_water_met,
                unmet_drink_water,
                spill,
                downstream_release,
                total_inflow,
            });
        }

        periods.push(PeriodResult {
            period_index: day,
            start_day: day,
            end_day_exclusive: day + 1,
            node_results,
        });
    }

    periods
}

fn simulate_daily_summary(
    scenario: &Scenario,
    compiled: &CompiledNetwork,
    action_matrix: Option<&[f64]>,
) -> SimulationSummary {
    let node_count = scenario.nodes.len();
    let horizon_days = scenario.horizon_days();
    let max_delay = compiled.max_delay;
    let dt_days = scenario.settings.timestep_days;
    let mut reservoir_levels = scenario
        .nodes
        .iter()
        .map(|node| node.reservoir.initial_level)
        .collect::<Vec<_>>();
    let mut scheduled_arrivals = vec![vec![0.0; node_count]; horizon_days + max_delay + 1];
    let mut summary = SimulationSummary::default();

    for day in 0..horizon_days {
        let mut arrivals = scheduled_arrivals[day].clone();

        for &node_index in &compiled.topological_order {
            let node = &scenario.nodes[node_index];
            let upstream_inflow = arrivals[node_index];
            let catchment_inflow = node.catchment_inflow.value_at(day) * dt_days;
            let total_inflow = catchment_inflow + upstream_inflow;
            let mut available = reservoir_levels[node_index] + total_inflow;

            let evaporation = (node.modules.evaporation.rate.value_at(day) * dt_days)
                .max(0.0)
                .min(available);
            available -= evaporation;

            let drink_water_demand =
                (node.modules.drink_water.daily_demand.value_at(day) * dt_days).max(0.0);
            let drink_water_met = drink_water_demand.min(available);
            let unmet_drink_water = drink_water_demand - drink_water_met;
            available -= drink_water_met;

            let food_water_demand = node.modules.food_production.water_demand(day, dt_days);
            let (food_produced, food_water_met) = node
                .modules
                .food_production
                .produce(available, day, dt_days);
            let unmet_food_water = food_water_demand - food_water_met;
            available -= food_water_met;

            let action_fraction =
                action_at(scenario, node, node_index, day, node_count, action_matrix);
            let max_release = (node.max_production * dt_days * action_fraction).max(0.0);
            let production_release = max_release.min(available);
            available -= production_release;

            let spill = (available - node.reservoir.max_capacity).max(0.0);
            reservoir_levels[node_index] = available.clamp(0.0, node.reservoir.max_capacity);

            let release_for_routing = production_release + spill;
            let mut downstream_release = 0.0;

            for &connection_index in &compiled.outgoing_connections[node_index] {
                let connection = &compiled.connections[connection_index];
                let routed = release_for_routing * connection.fraction;
                downstream_release += routed;

                if connection.delay == 0 {
                    arrivals[connection.to_index] += routed;
                } else {
                    scheduled_arrivals[day + connection.delay][connection.to_index] += routed;
                }
            }

            let energy_value =
                production_release * node.modules.energy.price_per_unit.value_at(day);

            summary.total_inflow += total_inflow;
            summary.total_evaporation += evaporation;
            summary.total_drink_water_met += drink_water_met;
            summary.total_unmet_drink_water += unmet_drink_water;
            summary.total_food_water_demand += food_water_demand;
            summary.total_food_water_met += food_water_met;
            summary.total_unmet_food_water += unmet_food_water;
            summary.total_food_produced += food_produced;
            summary.total_production_release += production_release;
            summary.total_energy_value += energy_value;
            summary.total_spill += spill;
            summary.total_downstream_release += downstream_release;
            summary.total_routing_loss += (release_for_routing - downstream_release).max(0.0);
        }
    }

    summary
}

fn aggregate_periods(
    daily_periods: &[PeriodResult],
    reporting: ReportingFrequency,
) -> Vec<PeriodResult> {
    match reporting {
        ReportingFrequency::Daily => daily_periods.to_vec(),
        ReportingFrequency::Monthly30Day => daily_periods
            .chunks(30)
            .enumerate()
            .map(|(period_index, chunk)| aggregate_chunk(period_index, chunk))
            .collect(),
    }
}

fn aggregate_chunk(period_index: usize, chunk: &[PeriodResult]) -> PeriodResult {
    let mut node_positions = HashMap::<String, usize>::new();
    let mut node_results = Vec::<NodeResult>::new();
    let mut node_counts = Vec::<usize>::new();

    for period in chunk {
        for node in &period.node_results {
            match node_positions.get(&node.node_id).copied() {
                Some(position) => {
                    node_counts[position] += 1;
                    let aggregate = &mut node_results[position];
                    aggregate.action += node.action;
                    aggregate.reservoir_level = node.reservoir_level;
                    aggregate.production_release += node.production_release;
                    aggregate.energy_value += node.energy_value;
                    aggregate.evaporation += node.evaporation;
                    aggregate.food_water_demand += node.food_water_demand;
                    aggregate.food_water_met += node.food_water_met;
                    aggregate.unmet_food_water += node.unmet_food_water;
                    aggregate.food_produced += node.food_produced;
                    aggregate.drink_water_met += node.drink_water_met;
                    aggregate.unmet_drink_water += node.unmet_drink_water;
                    aggregate.spill += node.spill;
                    aggregate.downstream_release += node.downstream_release;
                    aggregate.total_inflow += node.total_inflow;
                }
                None => {
                    let position = node_results.len();
                    node_positions.insert(node.node_id.clone(), position);
                    node_results.push(node.clone());
                    node_counts.push(1);
                }
            }
        }
    }

    for (index, aggregate) in node_results.iter_mut().enumerate() {
        let count = node_counts.get(index).copied().unwrap_or(1);
        aggregate.action /= count as f64;
    }

    PeriodResult {
        period_index,
        start_day: chunk
            .first()
            .map(|period| period.start_day)
            .unwrap_or_default(),
        end_day_exclusive: chunk
            .last()
            .map(|period| period.end_day_exclusive)
            .unwrap_or_default(),
        node_results,
    }
}

fn summarize(periods: &[PeriodResult]) -> SimulationSummary {
    let mut summary = SimulationSummary::default();

    for period in periods {
        for node in &period.node_results {
            summary.total_inflow += node.total_inflow;
            summary.total_evaporation += node.evaporation;
            summary.total_drink_water_met += node.drink_water_met;
            summary.total_unmet_drink_water += node.unmet_drink_water;
            summary.total_food_water_demand += node.food_water_demand;
            summary.total_food_water_met += node.food_water_met;
            summary.total_unmet_food_water += node.unmet_food_water;
            summary.total_food_produced += node.food_produced;
            summary.total_production_release += node.production_release;
            summary.total_energy_value += node.energy_value;
            summary.total_spill += node.spill;
            summary.total_downstream_release += node.downstream_release;

            let routed_source = node.production_release + node.spill;
            summary.total_routing_loss += (routed_source - node.downstream_release).max(0.0);
        }
    }

    summary
}

fn validate_scenario(scenario: &Scenario) -> Result<(), SimulationError> {
    if scenario.nodes.is_empty() {
        return Err(SimulationError::Validation(
            "scenario must contain at least one node".to_string(),
        ));
    }

    if scenario.settings.timestep_days <= 0.0 {
        return Err(SimulationError::Validation(
            "settings.timestep_days must be greater than zero".to_string(),
        ));
    }

    if let Some(horizon_days) = scenario.settings.horizon_days
        && horizon_days == 0
    {
        return Err(SimulationError::Validation(
            "settings.horizon_days must be at least one day".to_string(),
        ));
    }

    let mut node_ids = HashMap::<&str, usize>::new();
    for (node_index, node) in scenario.nodes.iter().enumerate() {
        if node_ids.insert(node.id.as_str(), node_index).is_some() {
            return Err(SimulationError::Validation(format!(
                "duplicate node id `{}`",
                node.id
            )));
        }

        validate_node(node)?;
    }

    for node in &scenario.nodes {
        let mut fraction_sum = 0.0;
        for connection in &node.connections {
            if !node_ids.contains_key(connection.node_id.as_str()) {
                return Err(SimulationError::Validation(format!(
                    "node `{}` connection references unknown node `{}`",
                    node.id, connection.node_id
                )));
            }

            if !(0.0..=1.0).contains(&connection.fraction) {
                return Err(SimulationError::Validation(format!(
                    "node `{}` connection to `{}` fraction must be between 0 and 1",
                    node.id, connection.node_id
                )));
            }

            fraction_sum += connection.fraction;
        }

        if fraction_sum > 1.0 + FLOAT_TOLERANCE {
            return Err(SimulationError::Validation(format!(
                "node `{}` connection fractions must sum to <= 1.0, found {fraction_sum}",
                node.id
            )));
        }
    }

    CompiledNetwork::build(&scenario.nodes)?;

    Ok(())
}

fn validate_node(node: &NodeConfig) -> Result<(), SimulationError> {
    if node.reservoir.initial_level < 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir.initial_level must be non-negative",
            node.id
        )));
    }

    if node.reservoir.max_capacity < 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir.max_capacity must be non-negative",
            node.id
        )));
    }

    if node.reservoir.initial_level > node.reservoir.max_capacity {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir.initial_level cannot exceed max_capacity",
            node.id
        )));
    }

    if node.max_production < 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` max_production must be non-negative",
            node.id
        )));
    }

    if node.modules.food_production.water_coefficient <= 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` food_production.water_coefficient must be greater than zero",
            node.id
        )));
    }

    node.catchment_inflow
        .validate(&format!("node `{}` catchment_inflow", node.id))
        .map_err(SimulationError::Validation)?;
    node.modules
        .evaporation
        .rate
        .validate(&format!("node `{}` evaporation", node.id))
        .map_err(SimulationError::Validation)?;
    node.modules
        .drink_water
        .daily_demand
        .validate(&format!("node `{}` drink_water", node.id))
        .map_err(SimulationError::Validation)?;
    node.modules
        .food_production
        .max_food_units
        .validate(&format!("node `{}` food_production", node.id))
        .map_err(SimulationError::Validation)?;
    node.modules
        .energy
        .price_per_unit
        .validate(&format!("node `{}` energy", node.id))
        .map_err(SimulationError::Validation)?;
    if let Some(actions) = &node.actions {
        actions
            .production_level
            .validate(&format!("node `{}` actions.production_level", node.id))
            .map_err(SimulationError::Validation)?;
    }

    Ok(())
}

#[derive(Clone, Debug)]
struct CompiledConnection {
    to_index: usize,
    fraction: f64,
    delay: usize,
}

#[derive(Clone, Debug)]
struct CompiledNetwork {
    topological_order: Vec<usize>,
    outgoing_connections: Vec<Vec<usize>>,
    connections: Vec<CompiledConnection>,
    max_delay: usize,
}

impl CompiledNetwork {
    fn build(nodes: &[NodeConfig]) -> Result<Self, SimulationError> {
        let node_index = nodes
            .iter()
            .enumerate()
            .map(|(index, node)| (node.id.clone(), index))
            .collect::<HashMap<_, _>>();
        let mut indegree = vec![0usize; nodes.len()];
        let mut outgoing_connections = vec![Vec::<usize>::new(); nodes.len()];
        let mut connections = Vec::<CompiledConnection>::new();
        let mut max_delay = 0;

        for (from_index, node) in nodes.iter().enumerate() {
            for connection in &node.connections {
                let Some(&to_index) = node_index.get(&connection.node_id) else {
                    return Err(SimulationError::Validation(format!(
                        "node `{}` connection references unknown node `{}`",
                        node.id, connection.node_id
                    )));
                };

                indegree[to_index] += 1;
                max_delay = max_delay.max(connection.delay);
                outgoing_connections[from_index].push(connections.len());
                connections.push(CompiledConnection {
                    to_index,
                    fraction: connection.fraction,
                    delay: connection.delay,
                });
            }
        }

        let topological_order = topological_order(&outgoing_connections, &connections, indegree)?;

        Ok(Self {
            topological_order,
            outgoing_connections,
            connections,
            max_delay,
        })
    }
}

fn topological_order(
    outgoing_connections: &[Vec<usize>],
    connections: &[CompiledConnection],
    indegree: Vec<usize>,
) -> Result<Vec<usize>, SimulationError> {
    let mut queue = VecDeque::new();
    for (node_index, &incoming_edges) in indegree.iter().enumerate() {
        if incoming_edges == 0 {
            queue.push_back(node_index);
        }
    }

    let mut order = Vec::with_capacity(indegree.len());
    let mut indegree_mut = indegree;

    while let Some(current_node_index) = queue.pop_front() {
        order.push(current_node_index);

        for &connection_index in &outgoing_connections[current_node_index] {
            let next_index = connections[connection_index].to_index;
            indegree_mut[next_index] -= 1;

            if indegree_mut[next_index] == 0 {
                queue.push_back(next_index);
            }
        }
    }

    if order.len() != outgoing_connections.len() {
        return Err(SimulationError::Validation(
            "node graph must be acyclic".to_string(),
        ));
    }

    Ok(order)
}

#[cfg(test)]
mod tests {
    use crate::{
        PreparedScenario,
        model::{
            ConnectionConfig, DrinkWaterModule, EnergyModule, EvaporationModule,
            FoodProductionModule, ModuleSeries, ModuleSourceType, NodeActions, NodeConfig,
            NodeModules, ReportingFrequency, ReservoirConfig, Scenario, SimulationSettings,
        },
        simulate, simulate_with_actions,
    };

    fn node(id: &str, inflow: f64, connections: Vec<ConnectionConfig>) -> NodeConfig {
        NodeConfig {
            id: id.to_string(),
            reservoir: ReservoirConfig {
                initial_level: 0.0,
                max_capacity: 1_000.0,
            },
            max_production: 1_000.0,
            catchment_inflow: ModuleSeries::constant(inflow),
            connections,
            modules: NodeModules::default(),
            actions: None,
        }
    }

    #[test]
    fn applies_documented_water_balance_priority() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![NodeConfig {
                id: "reservoir".to_string(),
                reservoir: ReservoirConfig {
                    initial_level: 50.0,
                    max_capacity: 100.0,
                },
                max_production: 10.0,
                catchment_inflow: ModuleSeries::constant(20.0),
                connections: vec![],
                actions: None,
                modules: NodeModules {
                    evaporation: EvaporationModule {
                        rate: ModuleSeries::constant(5.0),
                    },
                    drink_water: DrinkWaterModule {
                        daily_demand: ModuleSeries::constant(15.0),
                    },
                    food_production: FoodProductionModule {
                        water_coefficient: 2.0,
                        max_food_units: ModuleSeries::constant(8.0),
                    },
                    energy: EnergyModule {
                        price_per_unit: ModuleSeries::constant(3.0),
                    },
                },
            }],
        };

        let result = simulate(&scenario).expect("simulation should succeed");
        let node = &result.periods[0].node_results[0];

        assert_eq!(node.evaporation, 5.0);
        assert_eq!(node.drink_water_met, 15.0);
        assert_eq!(node.food_water_demand, 16.0);
        assert_eq!(node.food_water_met, 16.0);
        assert_eq!(node.unmet_food_water, 0.0);
        assert_eq!(node.food_produced, 8.0);
        assert_eq!(node.production_release, 10.0);
        assert_eq!(node.energy_value, 30.0);
        assert_eq!(node.reservoir_level, 24.0);
    }

    #[test]
    fn preserves_per_node_mass_balance_with_spill() {
        let water_coefficient = 2.0;
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![NodeConfig {
                id: "reservoir".to_string(),
                reservoir: ReservoirConfig {
                    initial_level: 30.0,
                    max_capacity: 40.0,
                },
                max_production: 25.0,
                catchment_inflow: ModuleSeries::constant(100.0),
                connections: vec![],
                actions: None,
                modules: NodeModules {
                    evaporation: EvaporationModule {
                        rate: ModuleSeries::constant(10.0),
                    },
                    drink_water: DrinkWaterModule {
                        daily_demand: ModuleSeries::constant(20.0),
                    },
                    food_production: FoodProductionModule {
                        water_coefficient,
                        max_food_units: ModuleSeries::constant(15.0),
                    },
                    energy: EnergyModule::default(),
                },
            }],
        };

        let result = simulate(&scenario).expect("simulation should succeed");
        let node = &result.periods[0].node_results[0];
        let starting_storage = scenario.nodes[0].reservoir.initial_level;
        let water_in = starting_storage + node.total_inflow;
        let water_out = node.evaporation
            + node.drink_water_met
            + node.food_water_met
            + node.production_release
            + node.spill
            + node.reservoir_level;

        assert_approx_eq(water_in, water_out);
        assert_eq!(node.food_water_demand, 30.0);
        assert_eq!(node.food_water_met, 30.0);
        assert_eq!(node.unmet_food_water, 0.0);
        assert_eq!(node.spill, 5.0);
        assert_eq!(node.reservoir_level, 40.0);
    }

    #[test]
    fn reports_unmet_food_water_when_available_water_is_short() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![NodeConfig {
                id: "farm".to_string(),
                reservoir: ReservoirConfig {
                    initial_level: 5.0,
                    max_capacity: 100.0,
                },
                max_production: 100.0,
                catchment_inflow: ModuleSeries::constant(5.0),
                connections: vec![],
                actions: None,
                modules: NodeModules {
                    evaporation: EvaporationModule::default(),
                    drink_water: DrinkWaterModule::default(),
                    food_production: FoodProductionModule {
                        water_coefficient: 2.0,
                        max_food_units: ModuleSeries::constant(20.0),
                    },
                    energy: EnergyModule::default(),
                },
            }],
        };

        let result = simulate(&scenario).expect("food shortfall should simulate");
        let node = &result.periods[0].node_results[0];

        assert_eq!(node.food_water_demand, 40.0);
        assert_eq!(node.food_water_met, 10.0);
        assert_eq!(node.unmet_food_water, 30.0);
        assert_eq!(node.food_produced, 5.0);
        assert_eq!(node.production_release, 0.0);
    }

    #[test]
    fn empty_reservoir_has_no_evaporation_or_release() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![NodeConfig {
                id: "dry".to_string(),
                reservoir: ReservoirConfig {
                    initial_level: 0.0,
                    max_capacity: 100.0,
                },
                max_production: 100.0,
                catchment_inflow: ModuleSeries::constant(0.0),
                connections: vec![],
                actions: None,
                modules: NodeModules {
                    evaporation: EvaporationModule {
                        rate: ModuleSeries::constant(10.0),
                    },
                    drink_water: DrinkWaterModule::default(),
                    food_production: FoodProductionModule::default(),
                    energy: EnergyModule::default(),
                },
            }],
        };

        let result = simulate(&scenario).expect("empty reservoir should simulate");
        let node = &result.periods[0].node_results[0];

        assert_eq!(node.evaporation, 0.0);
        assert_eq!(node.production_release, 0.0);
        assert_eq!(node.spill, 0.0);
        assert_eq!(node.reservoir_level, 0.0);
    }

    #[test]
    fn evaporation_is_capped_by_available_water() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![NodeConfig {
                id: "nearly-dry".to_string(),
                reservoir: ReservoirConfig {
                    initial_level: 2.0,
                    max_capacity: 100.0,
                },
                max_production: 100.0,
                catchment_inflow: ModuleSeries::constant(3.0),
                connections: vec![],
                actions: None,
                modules: NodeModules {
                    evaporation: EvaporationModule {
                        rate: ModuleSeries::constant(10.0),
                    },
                    drink_water: DrinkWaterModule {
                        daily_demand: ModuleSeries::constant(10.0),
                    },
                    food_production: FoodProductionModule::default(),
                    energy: EnergyModule::default(),
                },
            }],
        };

        let result = simulate(&scenario).expect("available-water cap should simulate");
        let node = &result.periods[0].node_results[0];

        assert_eq!(node.evaporation, 5.0);
        assert_eq!(node.drink_water_met, 0.0);
        assert_eq!(node.unmet_drink_water, 10.0);
        assert_eq!(node.production_release, 0.0);
        assert_eq!(node.reservoir_level, 0.0);
    }

    #[test]
    fn routes_zero_delay_release_in_same_timestep() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![
                node(
                    "upper",
                    100.0,
                    vec![ConnectionConfig {
                        node_id: "lower".to_string(),
                        fraction: 1.0,
                        delay: 0,
                    }],
                ),
                node("lower", 0.0, vec![]),
            ],
        };

        let result = simulate(&scenario).expect("simulation should succeed");
        let upper = &result.periods[0].node_results[0];
        let lower = &result.periods[0].node_results[1];

        assert_eq!(upper.production_release, 100.0);
        assert_eq!(lower.total_inflow, 100.0);
    }

    #[test]
    fn routes_delayed_release_to_future_timestep() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(2),
                ..SimulationSettings::default()
            },
            nodes: vec![
                node(
                    "upper",
                    100.0,
                    vec![ConnectionConfig {
                        node_id: "lower".to_string(),
                        fraction: 1.0,
                        delay: 1,
                    }],
                ),
                node("lower", 0.0, vec![]),
            ],
        };

        let result = simulate(&scenario).expect("simulation should succeed");
        let day_0_lower = &result.periods[0].node_results[1];
        let day_1_lower = &result.periods[1].node_results[1];

        assert_eq!(day_0_lower.total_inflow, 0.0);
        assert_eq!(day_1_lower.total_inflow, 100.0);
    }

    #[test]
    fn monthly_reporting_sums_step_outputs() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(31),
                reporting: ReportingFrequency::Monthly30Day,
                ..SimulationSettings::default()
            },
            nodes: vec![node("source", 10.0, vec![])],
        };

        let result = simulate(&scenario).expect("simulation should succeed");

        assert_eq!(result.periods.len(), 2);
        assert_eq!(result.periods[0].node_results[0].total_inflow, 300.0);
        assert_eq!(result.periods[1].node_results[0].total_inflow, 10.0);
    }

    #[test]
    fn rejects_cycles() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![
                node(
                    "a",
                    1.0,
                    vec![ConnectionConfig {
                        node_id: "b".to_string(),
                        fraction: 1.0,
                        delay: 0,
                    }],
                ),
                node(
                    "b",
                    0.0,
                    vec![ConnectionConfig {
                        node_id: "a".to_string(),
                        fraction: 1.0,
                        delay: 0,
                    }],
                ),
            ],
        };

        let error = simulate(&scenario).expect_err("cycle should be rejected");
        assert!(error.to_string().contains("acyclic"));
    }

    #[test]
    fn clamps_production_level_fraction_to_action_bounds() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                production_level_fraction: 2.0,
                ..SimulationSettings::default()
            },
            nodes: vec![node("source", 100.0, vec![])],
        };

        let result = simulate(&scenario).expect("out-of-range action should be clamped");
        let source = &result.periods[0].node_results[0];

        assert_eq!(source.production_release, 100.0);
        assert_eq!(source.action, 1.0);
    }

    #[test]
    fn applies_per_node_time_series_actions() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(2),
                production_level_fraction: 1.0,
                ..SimulationSettings::default()
            },
            nodes: vec![NodeConfig {
                id: "source".to_string(),
                reservoir: ReservoirConfig {
                    initial_level: 0.0,
                    max_capacity: 1_000.0,
                },
                max_production: 100.0,
                catchment_inflow: ModuleSeries::constant(100.0),
                connections: vec![],
                modules: NodeModules::default(),
                actions: Some(NodeActions {
                    production_level: ModuleSeries {
                        source_type: Some(ModuleSourceType::Csv),
                        values: vec![0.25, 0.75],
                        ..ModuleSeries::constant(1.0)
                    },
                }),
            }],
        };

        let result = simulate(&scenario).expect("time-series actions should simulate");
        let day_0 = &result.periods[0].node_results[0];
        let day_1 = &result.periods[1].node_results[0];

        assert_eq!(day_0.action, 0.25);
        assert_eq!(day_0.production_release, 25.0);
        assert_eq!(day_1.action, 0.75);
        assert_eq!(day_1.production_release, 75.0);
    }

    #[test]
    fn prepared_scenario_accepts_flat_action_matrix() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(2),
                production_level_fraction: 1.0,
                ..SimulationSettings::default()
            },
            nodes: vec![
                node("upper", 1_000.0, vec![]),
                node("lower", 1_000.0, vec![]),
            ],
        };
        let prepared = PreparedScenario::try_new(scenario.clone())
            .expect("scenario should prepare once for repeated optimization runs");

        assert_eq!(
            prepared.node_ids(),
            &["upper".to_string(), "lower".to_string()]
        );
        assert_eq!(prepared.expected_action_len(), 4);

        let result = prepared
            .simulate_with_actions(&[0.25, 0.5, 0.75, 1.0])
            .expect("flat action matrix should simulate");

        assert_eq!(result.periods[0].node_results[0].action, 0.25);
        assert_eq!(result.periods[0].node_results[0].production_release, 250.0);
        assert_eq!(result.periods[0].node_results[1].action, 0.5);
        assert_eq!(result.periods[0].node_results[1].production_release, 500.0);
        assert_eq!(result.periods[1].node_results[0].action, 0.75);
        assert_eq!(result.periods[1].node_results[1].action, 1.0);

        let one_shot = simulate_with_actions(&scenario, &[0.25, 0.5, 0.75, 1.0])
            .expect("one-shot action matrix should still work");
        assert_eq!(
            one_shot.summary.total_production_release,
            result.summary.total_production_release
        );

        let summary = prepared
            .simulate_summary_with_actions(&[0.25, 0.5, 0.75, 1.0])
            .expect("summary-only action matrix should simulate");
        assert_eq!(
            summary.total_production_release,
            result.summary.total_production_release
        );
        assert_eq!(
            summary.total_energy_value,
            result.summary.total_energy_value
        );
    }

    #[test]
    fn rejects_connection_fraction_sum_above_one() {
        let scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![
                node(
                    "source",
                    100.0,
                    vec![
                        ConnectionConfig {
                            node_id: "left".to_string(),
                            fraction: 0.7,
                            delay: 0,
                        },
                        ConnectionConfig {
                            node_id: "right".to_string(),
                            fraction: 0.4,
                            delay: 0,
                        },
                    ],
                ),
                node("left", 0.0, vec![]),
                node("right", 0.0, vec![]),
            ],
        };

        let error = simulate(&scenario).expect_err("oversubscribed routing should be rejected");

        assert!(error.to_string().contains("fractions must sum to <= 1.0"));
    }

    fn assert_approx_eq(left: f64, right: f64) {
        assert!(
            (left - right).abs() < 1e-9,
            "expected {left} to approximately equal {right}"
        );
    }
}
