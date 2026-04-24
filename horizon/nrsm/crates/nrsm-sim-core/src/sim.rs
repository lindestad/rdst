use std::collections::{HashMap, VecDeque};

use crate::{
    error::SimulationError,
    model::{
        DeliveryResult, EdgeConfig, EdgeResult, EngineTimeStep, HydropowerPlant, HydropowerResult,
        IrrigationDemand, IrrigationResult, NetworkConfig, NodeConfig, NodeKind, NodeResult,
        PeriodResult, ReportingFrequency, ReservoirConfig, Scenario, SimulationResult,
        SimulationSummary,
    },
};

const FLOAT_TOLERANCE: f64 = 1e-9;

pub fn simulate(scenario: &Scenario) -> Result<SimulationResult, SimulationError> {
    validate_scenario(scenario)?;
    let compiled = CompiledNetwork::build(&scenario.network)?;

    let daily_periods = simulate_daily_periods(scenario, &compiled);
    let periods = aggregate_periods(&daily_periods, scenario.simulation.reporting);
    let summary = summarize(&periods);

    Ok(SimulationResult {
        metadata: scenario.metadata.clone(),
        engine_time_step: EngineTimeStep::Daily,
        reporting: scenario.simulation.reporting,
        summary,
        periods,
    })
}

fn simulate_daily_periods(scenario: &Scenario, compiled: &CompiledNetwork) -> Vec<PeriodResult> {
    let node_count = scenario.network.nodes.len();
    let mut storage: Vec<f64> = scenario
        .network
        .nodes
        .iter()
        .map(|node| {
            node.reservoir
                .as_ref()
                .map(|reservoir| reservoir.initial_storage)
                .unwrap_or_default()
        })
        .collect();

    let mut periods = Vec::with_capacity(scenario.simulation.horizon_days);

    for day in 0..scenario.simulation.horizon_days {
        let mut arrivals = vec![0.0; node_count];
        let mut node_results = Vec::with_capacity(node_count);
        let mut edge_results = Vec::new();
        let mut basin_exit_flow = 0.0;
        let mut total_incoming_flow = 0.0;
        let mut total_local_inflow = 0.0;
        let mut total_edge_loss = 0.0;

        for &node_index in &compiled.topological_order {
            let node = &scenario.network.nodes[node_index];
            let incoming_flow = arrivals[node_index];
            let local_inflow = node.local_inflow.value_at(day);
            let starting_storage = storage[node_index];
            let available_water = incoming_flow + local_inflow + starting_storage;

            let (drinking_result, remaining_after_drinking) =
                simulate_drinking(node.drinking_water.as_ref(), day, available_water);
            let (irrigation_result, remaining_after_irrigation) =
                simulate_irrigation(node.irrigation.as_ref(), day, remaining_after_drinking);

            let (downstream_outflow, ending_storage) =
                route_node_outflow(node.reservoir.as_ref(), day, remaining_after_irrigation);
            storage[node_index] = ending_storage;

            let hydropower_result =
                simulate_hydropower(node.hydropower.as_ref(), day, downstream_outflow);

            let outgoing_edges = &compiled.outgoing_edges[node_index];
            let mut routed_total = 0.0;

            for &edge_index in outgoing_edges {
                let edge = &scenario.network.edges[edge_index];
                let routed_flow = downstream_outflow * edge.flow_share;
                let lost_flow = routed_flow * edge.loss_fraction;
                let received_flow = routed_flow - lost_flow;
                let destination_index = compiled.node_index[&edge.to];

                arrivals[destination_index] += received_flow;
                routed_total += routed_flow;
                total_edge_loss += lost_flow;

                edge_results.push(EdgeResult {
                    edge_id: edge.id.clone(),
                    from_node: edge.from.clone(),
                    to_node: edge.to.clone(),
                    total_routed_flow: routed_flow,
                    total_lost_flow: lost_flow,
                    total_received_flow: received_flow,
                });
            }

            let node_basin_exit = (downstream_outflow - routed_total).max(0.0);
            basin_exit_flow += node_basin_exit;
            total_incoming_flow += incoming_flow;
            total_local_inflow += local_inflow;

            node_results.push(NodeResult {
                node_id: node.id.clone(),
                node_name: node.name.clone(),
                node_kind: node.kind,
                total_incoming_flow: incoming_flow,
                total_local_inflow: local_inflow,
                starting_storage,
                ending_storage,
                total_available_water: available_water,
                total_downstream_outflow: downstream_outflow,
                total_basin_exit_outflow: node_basin_exit,
                drinking_water: drinking_result,
                irrigation: irrigation_result,
                hydropower: hydropower_result,
            });
        }

        periods.push(PeriodResult {
            period_index: day,
            start_day: day,
            end_day_exclusive: day + 1,
            total_incoming_flow,
            total_local_inflow,
            total_edge_loss,
            total_basin_exit_flow: basin_exit_flow,
            node_results,
            edge_results,
        });
    }

    periods
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
    let mut edge_positions = HashMap::<String, usize>::new();
    let mut node_results = Vec::<NodeResult>::new();
    let mut edge_results = Vec::<EdgeResult>::new();

    for period in chunk {
        for node in &period.node_results {
            match node_positions.get(&node.node_id).copied() {
                Some(position) => {
                    let aggregate = &mut node_results[position];
                    aggregate.total_incoming_flow += node.total_incoming_flow;
                    aggregate.total_local_inflow += node.total_local_inflow;
                    aggregate.total_available_water += node.total_available_water;
                    aggregate.total_downstream_outflow += node.total_downstream_outflow;
                    aggregate.total_basin_exit_outflow += node.total_basin_exit_outflow;
                    aggregate.ending_storage = node.ending_storage;
                    merge_delivery(&mut aggregate.drinking_water, &node.drinking_water);
                    merge_irrigation(&mut aggregate.irrigation, &node.irrigation);
                    merge_hydropower(&mut aggregate.hydropower, &node.hydropower);
                }
                None => {
                    let position = node_results.len();
                    node_positions.insert(node.node_id.clone(), position);
                    node_results.push(node.clone());
                }
            }
        }

        for edge in &period.edge_results {
            match edge_positions.get(&edge.edge_id).copied() {
                Some(position) => {
                    let aggregate = &mut edge_results[position];
                    aggregate.total_routed_flow += edge.total_routed_flow;
                    aggregate.total_lost_flow += edge.total_lost_flow;
                    aggregate.total_received_flow += edge.total_received_flow;
                }
                None => {
                    let position = edge_results.len();
                    edge_positions.insert(edge.edge_id.clone(), position);
                    edge_results.push(edge.clone());
                }
            }
        }
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
        total_incoming_flow: chunk.iter().map(|period| period.total_incoming_flow).sum(),
        total_local_inflow: chunk.iter().map(|period| period.total_local_inflow).sum(),
        total_edge_loss: chunk.iter().map(|period| period.total_edge_loss).sum(),
        total_basin_exit_flow: chunk
            .iter()
            .map(|period| period.total_basin_exit_flow)
            .sum(),
        node_results,
        edge_results,
    }
}

fn summarize(periods: &[PeriodResult]) -> SimulationSummary {
    let mut summary = SimulationSummary::default();

    for period in periods {
        summary.total_incoming_flow += period.total_incoming_flow;
        summary.total_local_inflow += period.total_local_inflow;
        summary.total_edge_loss += period.total_edge_loss;
        summary.total_basin_exit_flow += period.total_basin_exit_flow;

        for node in &period.node_results {
            if let Some(drinking) = &node.drinking_water {
                summary.total_drinking_water_delivered += drinking.actual_delivery;
                summary.total_drinking_shortfall_to_minimum += drinking.shortfall_to_minimum;
            }

            if let Some(irrigation) = &node.irrigation {
                summary.total_irrigation_water_delivered += irrigation.water.actual_delivery;
                summary.total_food_produced += irrigation.food_produced;
                summary.total_irrigation_shortfall_to_minimum +=
                    irrigation.water.shortfall_to_minimum;
            }

            if let Some(hydropower) = &node.hydropower {
                summary.total_energy_generated += hydropower.energy_generated;
                summary.total_energy_shortfall_to_minimum += hydropower.shortfall_to_minimum;
            }
        }
    }

    summary
}

fn simulate_drinking(
    demand: Option<&crate::model::DrinkingWaterDemand>,
    day: usize,
    available_water: f64,
) -> (Option<DeliveryResult>, f64) {
    let Some(demand) = demand else {
        return (None, available_water);
    };

    let target = demand.target_daily_delivery.value_at(day);
    let minimum = demand
        .minimum_daily_delivery
        .as_ref()
        .map(|series| series.value_at(day))
        .unwrap_or(target);
    let actual = available_water.min(target);
    let remaining = available_water - actual;

    (
        Some(DeliveryResult {
            actual_delivery: actual,
            total_target: target,
            total_minimum_target: minimum,
            shortfall_to_target: (target - actual).max(0.0),
            shortfall_to_minimum: (minimum - actual).max(0.0),
        }),
        remaining,
    )
}

fn simulate_irrigation(
    demand: Option<&IrrigationDemand>,
    day: usize,
    available_water: f64,
) -> (Option<IrrigationResult>, f64) {
    let Some(demand) = demand else {
        return (None, available_water);
    };

    let target = demand.target_daily_delivery.value_at(day);
    let minimum = demand
        .minimum_daily_delivery
        .as_ref()
        .map(|series| series.value_at(day))
        .unwrap_or(target);
    let actual = available_water.min(target);
    let remaining = available_water - actual;

    (
        Some(IrrigationResult {
            water: DeliveryResult {
                actual_delivery: actual,
                total_target: target,
                total_minimum_target: minimum,
                shortfall_to_target: (target - actual).max(0.0),
                shortfall_to_minimum: (minimum - actual).max(0.0),
            },
            food_produced: actual * demand.food_per_unit_water,
        }),
        remaining,
    )
}

fn simulate_hydropower(
    plant: Option<&HydropowerPlant>,
    day: usize,
    downstream_outflow: f64,
) -> Option<HydropowerResult> {
    let plant = plant?;
    let turbine_capacity = plant.max_turbine_flow.value_at(day);
    let turbine_flow = downstream_outflow.min(turbine_capacity);
    let energy_generated = turbine_flow * plant.energy_per_unit_water;
    let minimum_energy = plant
        .minimum_daily_energy
        .as_ref()
        .map(|series| series.value_at(day))
        .unwrap_or_default();
    let target_energy = plant
        .target_daily_energy
        .as_ref()
        .map(|series| series.value_at(day))
        .unwrap_or(minimum_energy);

    Some(HydropowerResult {
        turbine_flow,
        energy_generated,
        total_target_energy: target_energy,
        total_minimum_energy: minimum_energy,
        shortfall_to_target: (target_energy - energy_generated).max(0.0),
        shortfall_to_minimum: (minimum_energy - energy_generated).max(0.0),
    })
}

fn route_node_outflow(
    reservoir: Option<&ReservoirConfig>,
    day: usize,
    water_after_uses: f64,
) -> (f64, f64) {
    let Some(reservoir) = reservoir else {
        return (water_after_uses, 0.0);
    };

    let desired_release = reservoir.target_release.value_at(day);
    let required_release_for_capacity = (water_after_uses - reservoir.capacity).max(0.0);
    let max_release_preserving_min = (water_after_uses - reservoir.min_storage).max(0.0);
    let release = required_release_for_capacity
        .max(desired_release.min(max_release_preserving_min))
        .min(water_after_uses);
    let ending_storage = (water_after_uses - release).clamp(0.0, reservoir.capacity);

    (release, ending_storage)
}

fn merge_delivery(target: &mut Option<DeliveryResult>, source: &Option<DeliveryResult>) {
    match (target.as_mut(), source) {
        (Some(target), Some(source)) => {
            target.actual_delivery += source.actual_delivery;
            target.total_target += source.total_target;
            target.total_minimum_target += source.total_minimum_target;
            target.shortfall_to_target += source.shortfall_to_target;
            target.shortfall_to_minimum += source.shortfall_to_minimum;
        }
        (None, Some(source)) => *target = Some(source.clone()),
        _ => {}
    }
}

fn merge_irrigation(target: &mut Option<IrrigationResult>, source: &Option<IrrigationResult>) {
    match (target.as_mut(), source) {
        (Some(target), Some(source)) => {
            target.food_produced += source.food_produced;
            target.water.actual_delivery += source.water.actual_delivery;
            target.water.total_target += source.water.total_target;
            target.water.total_minimum_target += source.water.total_minimum_target;
            target.water.shortfall_to_target += source.water.shortfall_to_target;
            target.water.shortfall_to_minimum += source.water.shortfall_to_minimum;
        }
        (None, Some(source)) => *target = Some(source.clone()),
        _ => {}
    }
}

fn merge_hydropower(target: &mut Option<HydropowerResult>, source: &Option<HydropowerResult>) {
    match (target.as_mut(), source) {
        (Some(target), Some(source)) => {
            target.turbine_flow += source.turbine_flow;
            target.energy_generated += source.energy_generated;
            target.total_target_energy += source.total_target_energy;
            target.total_minimum_energy += source.total_minimum_energy;
            target.shortfall_to_target += source.shortfall_to_target;
            target.shortfall_to_minimum += source.shortfall_to_minimum;
        }
        (None, Some(source)) => *target = Some(source.clone()),
        _ => {}
    }
}

fn validate_scenario(scenario: &Scenario) -> Result<(), SimulationError> {
    if scenario.simulation.horizon_days == 0 {
        return Err(SimulationError::Validation(
            "simulation horizon must be at least one day".to_string(),
        ));
    }

    let mut node_ids = HashMap::<&str, usize>::new();
    for (index, node) in scenario.network.nodes.iter().enumerate() {
        if node_ids.insert(node.id.as_str(), index).is_some() {
            return Err(SimulationError::Validation(format!(
                "duplicate node id `{}`",
                node.id
            )));
        }

        node.local_inflow
            .validate(&format!("node `{}` local inflow", node.id))
            .map_err(SimulationError::Validation)?;

        match (&node.kind, &node.reservoir) {
            (NodeKind::Reservoir, Some(reservoir)) => validate_reservoir(node, reservoir)?,
            (NodeKind::Reservoir, None) => {
                return Err(SimulationError::Validation(format!(
                    "reservoir node `{}` is missing a reservoir configuration",
                    node.id
                )));
            }
            (NodeKind::River, Some(_)) => {
                return Err(SimulationError::Validation(format!(
                    "river node `{}` cannot define a reservoir configuration",
                    node.id
                )));
            }
            (NodeKind::River, None) => {}
        }

        if let Some(drinking_water) = &node.drinking_water {
            validate_timeseries_pair(
                drinking_water.minimum_daily_delivery.as_ref(),
                &drinking_water.target_daily_delivery,
                &format!("node `{}` drinking water", node.id),
            )?;
        }

        if let Some(irrigation) = &node.irrigation {
            if irrigation.food_per_unit_water < 0.0 {
                return Err(SimulationError::Validation(format!(
                    "node `{}` irrigation food_per_unit_water must be non-negative",
                    node.id
                )));
            }

            validate_timeseries_pair(
                irrigation.minimum_daily_delivery.as_ref(),
                &irrigation.target_daily_delivery,
                &format!("node `{}` irrigation", node.id),
            )?;
        }

        if let Some(hydropower) = &node.hydropower {
            if hydropower.energy_per_unit_water < 0.0 {
                return Err(SimulationError::Validation(format!(
                    "node `{}` hydropower energy_per_unit_water must be non-negative",
                    node.id
                )));
            }

            hydropower
                .max_turbine_flow
                .validate(&format!("node `{}` hydropower max_turbine_flow", node.id))
                .map_err(SimulationError::Validation)?;

            if let Some(minimum) = &hydropower.minimum_daily_energy {
                minimum
                    .validate(&format!("node `{}` hydropower minimum energy", node.id))
                    .map_err(SimulationError::Validation)?;
            }

            if let Some(target) = &hydropower.target_daily_energy {
                target
                    .validate(&format!("node `{}` hydropower target energy", node.id))
                    .map_err(SimulationError::Validation)?;
            }
        }
    }

    let mut edge_ids = HashMap::<&str, usize>::new();
    let mut outgoing_share_by_node = vec![0.0; scenario.network.nodes.len()];

    for (index, edge) in scenario.network.edges.iter().enumerate() {
        if edge_ids.insert(edge.id.as_str(), index).is_some() {
            return Err(SimulationError::Validation(format!(
                "duplicate edge id `{}`",
                edge.id
            )));
        }

        if !(0.0..=1.0).contains(&edge.flow_share) {
            return Err(SimulationError::Validation(format!(
                "edge `{}` flow_share must be between 0 and 1",
                edge.id
            )));
        }

        if !(0.0..=1.0).contains(&edge.loss_fraction) {
            return Err(SimulationError::Validation(format!(
                "edge `{}` loss_fraction must be between 0 and 1",
                edge.id
            )));
        }

        let Some(from_index) = node_ids.get(edge.from.as_str()).copied() else {
            return Err(SimulationError::Validation(format!(
                "edge `{}` references unknown from node `{}`",
                edge.id, edge.from
            )));
        };

        if !node_ids.contains_key(edge.to.as_str()) {
            return Err(SimulationError::Validation(format!(
                "edge `{}` references unknown to node `{}`",
                edge.id, edge.to
            )));
        }

        outgoing_share_by_node[from_index] += edge.flow_share;
    }

    for (node_index, share_sum) in outgoing_share_by_node.iter().copied().enumerate() {
        let has_outgoing = scenario
            .network
            .edges
            .iter()
            .any(|edge| edge.from == scenario.network.nodes[node_index].id);

        if has_outgoing && (share_sum - 1.0).abs() > FLOAT_TOLERANCE {
            return Err(SimulationError::Validation(format!(
                "outgoing edge flow shares for node `{}` must sum to 1.0, found {share_sum}",
                scenario.network.nodes[node_index].id
            )));
        }
    }

    CompiledNetwork::build(&scenario.network)?;

    Ok(())
}

fn validate_reservoir(
    node: &NodeConfig,
    reservoir: &ReservoirConfig,
) -> Result<(), SimulationError> {
    if reservoir.capacity < 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir capacity must be non-negative",
            node.id
        )));
    }

    if reservoir.min_storage < 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir min_storage must be non-negative",
            node.id
        )));
    }

    if reservoir.initial_storage < 0.0 {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir initial_storage must be non-negative",
            node.id
        )));
    }

    if reservoir.min_storage > reservoir.capacity {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir min_storage cannot exceed capacity",
            node.id
        )));
    }

    if reservoir.initial_storage > reservoir.capacity {
        return Err(SimulationError::Validation(format!(
            "node `{}` reservoir initial_storage cannot exceed capacity",
            node.id
        )));
    }

    reservoir
        .target_release
        .validate(&format!("node `{}` reservoir target_release", node.id))
        .map_err(SimulationError::Validation)?;

    Ok(())
}

fn validate_timeseries_pair(
    minimum: Option<&crate::model::TimeSeries>,
    target: &crate::model::TimeSeries,
    label: &str,
) -> Result<(), SimulationError> {
    if let Some(minimum) = minimum {
        minimum
            .validate(&format!("{label} minimum"))
            .map_err(SimulationError::Validation)?;
    }

    target
        .validate(&format!("{label} target"))
        .map_err(SimulationError::Validation)?;

    Ok(())
}

struct CompiledNetwork {
    node_index: HashMap<String, usize>,
    topological_order: Vec<usize>,
    outgoing_edges: Vec<Vec<usize>>,
}

impl CompiledNetwork {
    fn build(network: &NetworkConfig) -> Result<Self, SimulationError> {
        let node_index = network
            .nodes
            .iter()
            .enumerate()
            .map(|(index, node)| (node.id.clone(), index))
            .collect::<HashMap<_, _>>();
        let mut indegree = vec![0usize; network.nodes.len()];
        let mut outgoing_edges = vec![Vec::<usize>::new(); network.nodes.len()];

        for (edge_index, edge) in network.edges.iter().enumerate() {
            let from_index = node_index[&edge.from];
            let to_index = node_index[&edge.to];
            indegree[to_index] += 1;
            outgoing_edges[from_index].push(edge_index);
        }

        let mut queue = VecDeque::new();
        for (node_index, &incoming_edges) in indegree.iter().enumerate() {
            if incoming_edges == 0 {
                queue.push_back(node_index);
            }
        }

        let mut topological_order = Vec::with_capacity(network.nodes.len());
        let mut indegree_mut = indegree;

        while let Some(current_node_index) = queue.pop_front() {
            topological_order.push(current_node_index);

            for &edge_index in &outgoing_edges[current_node_index] {
                let edge: &EdgeConfig = &network.edges[edge_index];
                let next_index = node_index[&edge.to];
                indegree_mut[next_index] -= 1;

                if indegree_mut[next_index] == 0 {
                    queue.push_back(next_index);
                }
            }
        }

        if topological_order.len() != network.nodes.len() {
            return Err(SimulationError::Validation(
                "river graph must be acyclic for the MVP simulator".to_string(),
            ));
        }

        Ok(Self {
            node_index,
            topological_order,
            outgoing_edges,
        })
    }
}

#[cfg(test)]
mod tests {
    use crate::{
        model::{
            NetworkConfig, NodeConfig, NodeKind, ReportingFrequency, Scenario, ScenarioMetadata,
            SimulationConfig, TimeSeries,
        },
        simulate,
    };

    use super::{EdgeConfig, HydropowerPlant, IrrigationDemand, ReservoirConfig};

    #[test]
    fn daily_engine_supports_monthly_reporting() {
        let scenario = Scenario {
            metadata: ScenarioMetadata {
                name: "test".to_string(),
                description: None,
            },
            simulation: SimulationConfig {
                horizon_days: 31,
                reporting: ReportingFrequency::Monthly30Day,
            },
            network: NetworkConfig {
                nodes: vec![
                    NodeConfig {
                        id: "source".to_string(),
                        name: "Source".to_string(),
                        kind: NodeKind::River,
                        local_inflow: TimeSeries::Constant { value: 100.0 },
                        reservoir: None,
                        drinking_water: None,
                        irrigation: None,
                        hydropower: None,
                    },
                    NodeConfig {
                        id: "reservoir".to_string(),
                        name: "Reservoir".to_string(),
                        kind: NodeKind::Reservoir,
                        local_inflow: TimeSeries::Constant { value: 0.0 },
                        reservoir: Some(ReservoirConfig {
                            capacity: 500.0,
                            min_storage: 100.0,
                            initial_storage: 200.0,
                            target_release: TimeSeries::Constant { value: 80.0 },
                        }),
                        drinking_water: None,
                        irrigation: Some(IrrigationDemand {
                            minimum_daily_delivery: Some(TimeSeries::Constant { value: 10.0 }),
                            target_daily_delivery: TimeSeries::Constant { value: 20.0 },
                            food_per_unit_water: 2.0,
                        }),
                        hydropower: Some(HydropowerPlant {
                            minimum_daily_energy: Some(TimeSeries::Constant { value: 20.0 }),
                            target_daily_energy: None,
                            max_turbine_flow: TimeSeries::Constant { value: 50.0 },
                            energy_per_unit_water: 0.5,
                        }),
                    },
                ],
                edges: vec![EdgeConfig {
                    id: "source_to_reservoir".to_string(),
                    from: "source".to_string(),
                    to: "reservoir".to_string(),
                    flow_share: 1.0,
                    loss_fraction: 0.1,
                }],
            },
        };

        let result = simulate(&scenario).expect("simulation should succeed");

        assert_eq!(result.periods.len(), 2);
        assert_eq!(result.periods[0].start_day, 0);
        assert_eq!(result.periods[0].end_day_exclusive, 30);
        assert_eq!(result.periods[1].start_day, 30);
        assert_eq!(result.periods[1].end_day_exclusive, 31);
        assert!(result.summary.total_food_produced > 0.0);
        assert!(result.summary.total_energy_generated > 0.0);
    }

    #[test]
    fn detects_cycles() {
        let scenario = Scenario {
            metadata: ScenarioMetadata {
                name: "cyclic".to_string(),
                description: None,
            },
            simulation: SimulationConfig {
                horizon_days: 1,
                reporting: ReportingFrequency::Daily,
            },
            network: NetworkConfig {
                nodes: vec![
                    NodeConfig {
                        id: "a".to_string(),
                        name: "A".to_string(),
                        kind: NodeKind::River,
                        local_inflow: TimeSeries::Constant { value: 1.0 },
                        reservoir: None,
                        drinking_water: None,
                        irrigation: None,
                        hydropower: None,
                    },
                    NodeConfig {
                        id: "b".to_string(),
                        name: "B".to_string(),
                        kind: NodeKind::River,
                        local_inflow: TimeSeries::Constant { value: 0.0 },
                        reservoir: None,
                        drinking_water: None,
                        irrigation: None,
                        hydropower: None,
                    },
                ],
                edges: vec![
                    EdgeConfig {
                        id: "a_to_b".to_string(),
                        from: "a".to_string(),
                        to: "b".to_string(),
                        flow_share: 1.0,
                        loss_fraction: 0.0,
                    },
                    EdgeConfig {
                        id: "b_to_a".to_string(),
                        from: "b".to_string(),
                        to: "a".to_string(),
                        flow_share: 1.0,
                        loss_fraction: 0.0,
                    },
                ],
            },
        };

        let error = simulate(&scenario).expect_err("cycle should be rejected");
        assert!(error.to_string().contains("acyclic"));
    }
}
