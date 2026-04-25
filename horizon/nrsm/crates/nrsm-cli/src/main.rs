use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};

use nrsm_sim_core::{
    ModuleSeries, ModuleSourceType, NodeActions, NodeResult, PeriodResult, Scenario,
    SimulationResult, simulate,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = parse_args()?;
    let scenario_contents = fs::read_to_string(&cli.scenario_path)?;
    let mut scenario: Scenario = serde_yaml::from_str(&scenario_contents)?;
    let base_dir = cli
        .scenario_path
        .parent()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    if let Some(actions_dir) = &cli.actions_dir {
        apply_action_overrides(&mut scenario, actions_dir, &cli.action_column)?;
    }
    if let Some(initial_levels_path) = &cli.initial_levels_path {
        apply_initial_level_overrides(&mut scenario, initial_levels_path)?;
    }
    scenario.load_module_csvs(base_dir)?;
    let result = simulate(&scenario)?;

    if let Some(results_dir) = &cli.results_dir {
        let outputs = write_result_csvs(&result, results_dir)?;
        eprintln!(
            "Wrote {} simulation CSV files to {}",
            outputs.len(),
            results_dir.display()
        );
    }

    match cli.output {
        OutputFormat::Yaml => println!("{}", serde_yaml::to_string(&result)?),
        OutputFormat::Json if cli.pretty => println!("{}", serde_json::to_string_pretty(&result)?),
        OutputFormat::Json => println!("{}", serde_json::to_string(&result)?),
    }

    Ok(())
}

#[derive(Debug)]
struct Cli {
    scenario_path: PathBuf,
    output: OutputFormat,
    pretty: bool,
    results_dir: Option<PathBuf>,
    actions_dir: Option<PathBuf>,
    action_column: String,
    initial_levels_path: Option<PathBuf>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum OutputFormat {
    Yaml,
    Json,
}

fn parse_args() -> Result<Cli, Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let mut scenario_path = None;
    let mut output = OutputFormat::Yaml;
    let mut pretty = false;
    let mut results_dir = None;
    let mut actions_dir = None;
    let mut action_column = "scenario_1".to_string();
    let mut initial_levels_path = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--pretty" => pretty = true,
            "--json" => output = OutputFormat::Json,
            "--yaml" => output = OutputFormat::Yaml,
            "--output" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --output".into());
                };
                output = parse_output_format(&value)?;
            }
            "--results-dir" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --results-dir".into());
                };
                results_dir = Some(PathBuf::from(value));
            }
            "--actions-dir" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --actions-dir".into());
                };
                actions_dir = Some(PathBuf::from(value));
            }
            "--action-column" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --action-column".into());
                };
                action_column = value;
            }
            "--initial-levels" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --initial-levels".into());
                };
                initial_levels_path = Some(PathBuf::from(value));
            }
            "--help" | "-h" => {
                print_help();
                std::process::exit(0);
            }
            value if value.starts_with('-') => {
                return Err(format!("unknown argument `{value}`").into());
            }
            value => {
                if scenario_path.is_some() {
                    return Err("expected a single scenario path".into());
                }
                scenario_path = Some(PathBuf::from(value));
            }
        }
    }

    let Some(scenario_path) = scenario_path else {
        print_help();
        return Err("missing scenario path".into());
    };

    Ok(Cli {
        scenario_path,
        output,
        pretty,
        results_dir,
        actions_dir,
        action_column,
        initial_levels_path,
    })
}

fn parse_output_format(value: &str) -> Result<OutputFormat, Box<dyn std::error::Error>> {
    match value {
        "yaml" => Ok(OutputFormat::Yaml),
        "json" => Ok(OutputFormat::Json),
        _ => Err(format!("unsupported output format `{value}`; expected `yaml` or `json`").into()),
    }
}

fn print_help() {
    eprintln!(
        "Usage: nrsm-cli <SCENARIO_PATH> [--output yaml|json] [--json] [--yaml] [--pretty] [--results-dir DIR] [--actions-dir DIR] [--action-column COLUMN] [--initial-levels FILE]"
    );
}

fn apply_initial_level_overrides(
    scenario: &mut Scenario,
    path: &Path,
) -> Result<(), Box<dyn std::error::Error>> {
    let overrides = read_initial_level_overrides(path)?;
    let mut remaining = overrides.keys().cloned().collect::<BTreeSet<_>>();

    for node in &mut scenario.nodes {
        if let Some(initial_level) = overrides.get(&node.id) {
            node.reservoir.initial_level = *initial_level;
            remaining.remove(&node.id);
        }
    }

    if !remaining.is_empty() {
        let unknown_node_ids = remaining.into_iter().collect::<Vec<_>>().join(", ");
        return Err(format!(
            "initial level override references unknown node id(s): {unknown_node_ids}"
        )
        .into());
    }

    Ok(())
}

fn read_initial_level_overrides(
    path: &Path,
) -> Result<BTreeMap<String, f64>, Box<dyn std::error::Error>> {
    let contents = fs::read_to_string(path)?;
    let value: serde_yaml::Value = serde_yaml::from_str(&contents)?;

    if let Some(levels) = value.get("initial_levels") {
        return parse_initial_level_map(levels, "initial_levels");
    }

    if let Some(nodes) = value.get("nodes") {
        return parse_node_initial_levels(nodes);
    }

    parse_initial_level_map(&value, "top-level mapping")
}

fn parse_initial_level_map(
    value: &serde_yaml::Value,
    label: &str,
) -> Result<BTreeMap<String, f64>, Box<dyn std::error::Error>> {
    let Some(mapping) = value.as_mapping() else {
        return Err(format!("{label} must be a mapping from node id to initial level").into());
    };

    let mut levels = BTreeMap::new();
    for (key, entry_value) in mapping {
        let Some(node_id) = key.as_str() else {
            return Err(format!("{label} keys must be node id strings").into());
        };
        levels.insert(
            node_id.to_string(),
            parse_initial_level_value(entry_value, node_id)?,
        );
    }

    Ok(levels)
}

fn parse_node_initial_levels(
    value: &serde_yaml::Value,
) -> Result<BTreeMap<String, f64>, Box<dyn std::error::Error>> {
    let Some(nodes) = value.as_sequence() else {
        return Err("nodes must be a list of node objects".into());
    };

    let mut levels = BTreeMap::new();
    for node in nodes {
        let Some(node_id) = node.get("id").and_then(|id| id.as_str()) else {
            return Err("each node initial-level override must include an id".into());
        };
        let Some(initial_level) = node
            .get("reservoir")
            .and_then(|reservoir| reservoir.get("initial_level"))
        else {
            continue;
        };
        levels.insert(
            node_id.to_string(),
            parse_initial_level_value(initial_level, node_id)?,
        );
    }

    Ok(levels)
}

fn parse_initial_level_value(
    value: &serde_yaml::Value,
    node_id: &str,
) -> Result<f64, Box<dyn std::error::Error>> {
    if let Some(number) = value.as_f64() {
        return Ok(number);
    }
    if let Some(text) = value.as_str() {
        return Ok(text.parse()?);
    }
    Err(format!("initial level for node `{node_id}` must be numeric").into())
}

fn apply_action_overrides(
    scenario: &mut Scenario,
    actions_dir: &Path,
    action_column: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let actions_dir = if actions_dir.is_absolute() {
        actions_dir.to_path_buf()
    } else {
        std::env::current_dir()?.join(actions_dir)
    };

    for node in &mut scenario.nodes {
        let actions_path = action_path_for_node(&actions_dir, &node.id).ok_or_else(|| {
            format!(
                "missing action CSV for node `{}` in {}; expected `{}` or `{}`",
                node.id,
                actions_dir.display(),
                actions_dir
                    .join(format!("{}.actions.csv", node.id))
                    .display(),
                actions_dir.join(format!("{}.csv", node.id)).display()
            )
        })?;
        node.actions = Some(NodeActions {
            production_level: ModuleSeries {
                source_type: Some(ModuleSourceType::Csv),
                value: None,
                filepath: Some(actions_path),
                column: action_column.to_string(),
                values: Vec::new(),
            },
        });
    }

    Ok(())
}

fn action_path_for_node(actions_dir: &Path, node_id: &str) -> Option<PathBuf> {
    [
        actions_dir.join(format!("{node_id}.actions.csv")),
        actions_dir.join(format!("{node_id}.csv")),
    ]
    .into_iter()
    .find(|path| path.exists())
}

fn write_result_csvs(
    result: &SimulationResult,
    output_dir: impl AsRef<Path>,
) -> Result<Vec<PathBuf>, std::io::Error> {
    let output_dir = output_dir.as_ref();
    fs::create_dir_all(output_dir)?;

    let mut rows_by_node = BTreeMap::<String, Vec<String>>::new();
    for period in &result.periods {
        for node in &period.node_results {
            rows_by_node
                .entry(node.node_id.clone())
                .or_default()
                .push(render_node_result_row(period, node));
        }
    }

    let mut outputs = Vec::with_capacity(rows_by_node.len() + 1);
    for (node_id, rows) in rows_by_node {
        let path = output_dir.join(format!("{node_id}.csv"));
        let mut contents = String::new();
        contents.push_str(NODE_RESULT_HEADER);
        contents.push('\n');
        contents.push_str(&rows.join("\n"));
        contents.push('\n');
        fs::write(&path, contents)?;
        outputs.push(path);
    }

    let summary_path = output_dir.join("summary.csv");
    fs::write(&summary_path, render_summary_csv(result))?;
    outputs.push(summary_path);

    Ok(outputs)
}

const NODE_RESULT_HEADER: &str = "period_index,start_day,end_day_exclusive,duration_days,node_id,action,reservoir_level,total_inflow,evaporation,drink_water_met,unmet_drink_water,food_water_demand,food_water_met,unmet_food_water,food_produced,production_release,generated_electricity_kwh,generated_electricity_mwh,water_value_eur_per_m3,spill,release_for_routing,downstream_release,routing_loss,energy_value";

fn render_node_result_row(period: &PeriodResult, node: &NodeResult) -> String {
    let duration_days = period.end_day_exclusive - period.start_day;
    let release_for_routing = node.production_release + node.spill;
    let routing_loss = (release_for_routing - node.downstream_release).max(0.0);
    csv_row([
        period.period_index.to_string(),
        period.start_day.to_string(),
        period.end_day_exclusive.to_string(),
        duration_days.to_string(),
        node.node_id.clone(),
        node.action.to_string(),
        node.reservoir_level.to_string(),
        node.total_inflow.to_string(),
        node.evaporation.to_string(),
        node.drink_water_met.to_string(),
        node.unmet_drink_water.to_string(),
        node.food_water_demand.to_string(),
        node.food_water_met.to_string(),
        node.unmet_food_water.to_string(),
        node.food_produced.to_string(),
        node.production_release.to_string(),
        node.generated_electricity_kwh.to_string(),
        (node.generated_electricity_kwh / 1_000.0).to_string(),
        node.water_value_eur_per_m3.to_string(),
        node.spill.to_string(),
        release_for_routing.to_string(),
        node.downstream_release.to_string(),
        routing_loss.to_string(),
        node.energy_value.to_string(),
    ])
}

fn render_summary_csv(result: &SimulationResult) -> String {
    let mut contents = String::from(
        "period_index,start_day,end_day_exclusive,duration_days,total_inflow,total_evaporation,total_drink_water_met,total_unmet_drink_water,total_food_water_demand,total_food_water_met,total_unmet_food_water,total_food_produced,total_production_release,total_generated_electricity_kwh,total_generated_electricity_mwh,total_spill,total_release_for_routing,total_downstream_release,total_routing_loss,total_energy_value,terminal_reservoir_storage\n",
    );

    for period in &result.periods {
        let duration_days = period.end_day_exclusive - period.start_day;
        let mut total_inflow = 0.0;
        let mut total_evaporation = 0.0;
        let mut total_drink_water_met = 0.0;
        let mut total_unmet_drink_water = 0.0;
        let mut total_food_water_demand = 0.0;
        let mut total_food_water_met = 0.0;
        let mut total_unmet_food_water = 0.0;
        let mut total_food_produced = 0.0;
        let mut total_production_release = 0.0;
        let mut total_generated_electricity_kwh = 0.0;
        let mut total_spill = 0.0;
        let mut total_release_for_routing = 0.0;
        let mut total_downstream_release = 0.0;
        let mut total_routing_loss = 0.0;
        let mut total_energy_value = 0.0;
        let mut terminal_reservoir_storage = 0.0;

        for node in &period.node_results {
            let release_for_routing = node.production_release + node.spill;
            total_inflow += node.total_inflow;
            total_evaporation += node.evaporation;
            total_drink_water_met += node.drink_water_met;
            total_unmet_drink_water += node.unmet_drink_water;
            total_food_water_demand += node.food_water_demand;
            total_food_water_met += node.food_water_met;
            total_unmet_food_water += node.unmet_food_water;
            total_food_produced += node.food_produced;
            total_production_release += node.production_release;
            total_generated_electricity_kwh += node.generated_electricity_kwh;
            total_spill += node.spill;
            total_release_for_routing += release_for_routing;
            total_downstream_release += node.downstream_release;
            total_routing_loss += (release_for_routing - node.downstream_release).max(0.0);
            total_energy_value += node.energy_value;
            terminal_reservoir_storage += node.reservoir_level;
        }

        contents.push_str(&csv_row([
            period.period_index.to_string(),
            period.start_day.to_string(),
            period.end_day_exclusive.to_string(),
            duration_days.to_string(),
            total_inflow.to_string(),
            total_evaporation.to_string(),
            total_drink_water_met.to_string(),
            total_unmet_drink_water.to_string(),
            total_food_water_demand.to_string(),
            total_food_water_met.to_string(),
            total_unmet_food_water.to_string(),
            total_food_produced.to_string(),
            total_production_release.to_string(),
            total_generated_electricity_kwh.to_string(),
            (total_generated_electricity_kwh / 1_000.0).to_string(),
            total_spill.to_string(),
            total_release_for_routing.to_string(),
            total_downstream_release.to_string(),
            total_routing_loss.to_string(),
            total_energy_value.to_string(),
            terminal_reservoir_storage.to_string(),
        ]));
        contents.push('\n');
    }

    contents
}

fn csv_row(fields: impl IntoIterator<Item = String>) -> String {
    fields
        .into_iter()
        .map(|field| escape_csv_field(&field))
        .collect::<Vec<_>>()
        .join(",")
}

fn escape_csv_field(field: &str) -> String {
    let requires_quotes =
        field.contains(',') || field.contains('"') || field.contains('\n') || field.contains('\r');

    if !requires_quotes {
        return field.to_string();
    }

    format!("\"{}\"", field.replace('"', "\"\""))
}

#[cfg(test)]
mod tests {
    use std::fs;

    use nrsm_sim_core::{
        ConnectionConfig, ModuleSeries, NodeConfig, ReservoirConfig, Scenario, SimulationSettings,
        simulate,
    };

    use super::{apply_action_overrides, apply_initial_level_overrides, write_result_csvs};

    #[test]
    fn writes_per_node_and_summary_csvs() {
        let unique = format!(
            "nrsm-cli-result-csv-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
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
                        fraction: 0.75,
                        delay: 0,
                    }],
                ),
                node("lower", 0.0, vec![]),
            ],
        };
        let result = simulate(&scenario).expect("simulation should succeed");

        let outputs = write_result_csvs(&result, &dir).expect("csv output should be written");

        assert_eq!(outputs.len(), 3);
        let upper = fs::read_to_string(dir.join("upper.csv")).expect("upper csv should exist");
        assert!(upper.starts_with("period_index,start_day,end_day_exclusive"));
        assert!(upper.contains("release_for_routing"));
        assert!(upper.contains("routing_loss"));
        assert_eq!(upper.lines().count(), 3);

        let summary = fs::read_to_string(dir.join("summary.csv")).expect("summary should exist");
        assert!(summary.contains("total_release_for_routing"));
        assert_eq!(summary.lines().count(), 3);

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    #[test]
    fn applies_external_action_csv_directory() {
        let unique = format!(
            "nrsm-cli-actions-dir-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        fs::create_dir_all(&dir).expect("temporary directory should be created");
        fs::write(
            dir.join("upper.actions.csv"),
            "date,scenario_1,policy\n2020-01-01,1.0,0.5\n",
        )
        .expect("upper actions should be written");
        fs::write(
            dir.join("lower.actions.csv"),
            "date,scenario_1,policy\n2020-01-01,1.0,0.25\n",
        )
        .expect("lower actions should be written");

        let mut scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![node("upper", 100.0, vec![]), node("lower", 100.0, vec![])],
        };

        apply_action_overrides(&mut scenario, &dir, "policy")
            .expect("action overrides should apply");
        scenario
            .load_module_csvs(".")
            .expect("action CSVs should load");
        let result = simulate(&scenario).expect("simulation should succeed");

        assert_eq!(result.periods[0].node_results[0].action, 0.5);
        assert_eq!(result.periods[0].node_results[0].production_release, 50.0);
        assert_eq!(result.periods[0].node_results[1].action, 0.25);
        assert_eq!(result.periods[0].node_results[1].production_release, 25.0);

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    #[test]
    fn applies_initial_level_override_file() {
        let unique = format!(
            "nrsm-cli-initial-levels-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        fs::create_dir_all(&dir).expect("temporary directory should be created");
        let override_path = dir.join("initial-levels.yaml");
        fs::write(
            &override_path,
            "initial_levels:\n  upper: 250.0\n  lower: 125.0\n",
        )
        .expect("initial levels should be written");

        let mut scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![node("upper", 0.0, vec![]), node("lower", 0.0, vec![])],
        };

        apply_initial_level_overrides(&mut scenario, &override_path)
            .expect("initial level overrides should apply");

        assert_eq!(scenario.nodes[0].reservoir.initial_level, 250.0);
        assert_eq!(scenario.nodes[1].reservoir.initial_level, 125.0);

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    #[test]
    fn rejects_initial_level_overrides_for_unknown_nodes() {
        let unique = format!(
            "nrsm-cli-initial-levels-unknown-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(unique);
        fs::create_dir_all(&dir).expect("temporary directory should be created");
        let override_path = dir.join("initial-levels.yaml");
        fs::write(&override_path, "initial_levels:\n  missing: 250.0\n")
            .expect("initial levels should be written");

        let mut scenario = Scenario {
            settings: SimulationSettings {
                horizon_days: Some(1),
                ..SimulationSettings::default()
            },
            nodes: vec![node("upper", 0.0, vec![])],
        };

        let error = apply_initial_level_overrides(&mut scenario, &override_path)
            .expect_err("unknown node override should fail");
        assert!(
            error
                .to_string()
                .contains("initial level override references unknown node id")
        );

        fs::remove_dir_all(&dir).expect("temporary directory should be removed");
    }

    fn node(id: &str, inflow: f64, connections: Vec<ConnectionConfig>) -> NodeConfig {
        NodeConfig {
            id: id.to_string(),
            reservoir: ReservoirConfig {
                initial_level: 0.0,
                max_capacity: 1_000.0,
            },
            max_production: 100.0,
            catchment_inflow: ModuleSeries::constant(inflow),
            connections,
            modules: Default::default(),
            actions: None,
        }
    }
}
