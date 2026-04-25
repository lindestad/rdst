use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
};

use nrsm_sim_core::{NodeResult, PeriodResult, Scenario, SimulationResult, simulate};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = parse_args()?;
    let scenario_contents = fs::read_to_string(&cli.scenario_path)?;
    let mut scenario: Scenario = serde_yaml::from_str(&scenario_contents)?;
    let base_dir = cli
        .scenario_path
        .parent()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
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
        "Usage: nrsm-cli <SCENARIO_PATH> [--output yaml|json] [--json] [--yaml] [--pretty] [--results-dir DIR]"
    );
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

const NODE_RESULT_HEADER: &str = "period_index,start_day,end_day_exclusive,duration_days,node_id,action,reservoir_level,total_inflow,evaporation,drink_water_met,unmet_drink_water,food_produced,production_release,spill,release_for_routing,downstream_release,routing_loss,energy_value";

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
        node.food_produced.to_string(),
        node.production_release.to_string(),
        node.spill.to_string(),
        release_for_routing.to_string(),
        node.downstream_release.to_string(),
        routing_loss.to_string(),
        node.energy_value.to_string(),
    ])
}

fn render_summary_csv(result: &SimulationResult) -> String {
    let mut contents = String::from(
        "period_index,start_day,end_day_exclusive,duration_days,total_inflow,total_evaporation,total_drink_water_met,total_unmet_drink_water,total_food_produced,total_production_release,total_spill,total_release_for_routing,total_downstream_release,total_routing_loss,total_energy_value\n",
    );

    for period in &result.periods {
        let duration_days = period.end_day_exclusive - period.start_day;
        let mut total_inflow = 0.0;
        let mut total_evaporation = 0.0;
        let mut total_drink_water_met = 0.0;
        let mut total_unmet_drink_water = 0.0;
        let mut total_food_produced = 0.0;
        let mut total_production_release = 0.0;
        let mut total_spill = 0.0;
        let mut total_release_for_routing = 0.0;
        let mut total_downstream_release = 0.0;
        let mut total_routing_loss = 0.0;
        let mut total_energy_value = 0.0;

        for node in &period.node_results {
            let release_for_routing = node.production_release + node.spill;
            total_inflow += node.total_inflow;
            total_evaporation += node.evaporation;
            total_drink_water_met += node.drink_water_met;
            total_unmet_drink_water += node.unmet_drink_water;
            total_food_produced += node.food_produced;
            total_production_release += node.production_release;
            total_spill += node.spill;
            total_release_for_routing += release_for_routing;
            total_downstream_release += node.downstream_release;
            total_routing_loss += (release_for_routing - node.downstream_release).max(0.0);
            total_energy_value += node.energy_value;
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
            total_food_produced.to_string(),
            total_production_release.to_string(),
            total_spill.to_string(),
            total_release_for_routing.to_string(),
            total_downstream_release.to_string(),
            total_routing_loss.to_string(),
            total_energy_value.to_string(),
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

    use super::write_result_csvs;

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
            modules: Default::default(),
            actions: None,
        }
    }
}
