use std::{fs, path::PathBuf};

use nrsm_sim_core::{Scenario, simulate};

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
    eprintln!("Usage: nrsm-cli <SCENARIO_PATH> [--output yaml|json] [--json] [--yaml] [--pretty]");
}
