use std::{fs, path::PathBuf};

use nrsm_dataloader::{SnapshotOptions, write_seed_snapshot};
use nrsm_sim_core::{Scenario, simulate};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = parse_args()?;
    if let Command::DataloaderSeed(seed) = cli.command {
        let outputs = write_seed_snapshot(
            &seed.output_dir,
            &SnapshotOptions {
                start_date: seed.start_date,
                end_date: seed.end_date,
                n_scenarios: seed.n_scenarios,
            },
        )?;
        println!(
            "Wrote {} dataloader files to {}",
            outputs.len(),
            seed.output_dir.display()
        );
        return Ok(());
    }

    let Command::RunScenario(run) = cli.command else {
        unreachable!("all commands should be handled above");
    };
    let scenario_contents = fs::read_to_string(&run.scenario_path)?;
    let mut scenario: Scenario = serde_yaml::from_str(&scenario_contents)?;
    let base_dir = run
        .scenario_path
        .parent()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    scenario.load_module_csvs(base_dir)?;
    let result = simulate(&scenario)?;

    match run.output {
        OutputFormat::Yaml => println!("{}", serde_yaml::to_string(&result)?),
        OutputFormat::Json if run.pretty => println!("{}", serde_json::to_string_pretty(&result)?),
        OutputFormat::Json => println!("{}", serde_json::to_string(&result)?),
    }

    Ok(())
}

#[derive(Debug)]
struct Cli {
    command: Command,
}

#[derive(Debug)]
enum Command {
    RunScenario(RunScenarioCli),
    DataloaderSeed(DataloaderSeedCli),
}

#[derive(Debug)]
struct RunScenarioCli {
    scenario_path: PathBuf,
    output: OutputFormat,
    pretty: bool,
}

#[derive(Debug)]
struct DataloaderSeedCli {
    output_dir: PathBuf,
    start_date: String,
    end_date: String,
    n_scenarios: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum OutputFormat {
    Yaml,
    Json,
}

fn parse_args() -> Result<Cli, Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    if matches!(args.next().as_deref(), Some("dataloader")) {
        return parse_dataloader_args(args.collect());
    }

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
        command: Command::RunScenario(RunScenarioCli {
            scenario_path,
            output,
            pretty,
        }),
    })
}

fn parse_dataloader_args(args: Vec<String>) -> Result<Cli, Box<dyn std::error::Error>> {
    let mut args = args.into_iter();
    match args.next().as_deref() {
        Some("seed") => parse_dataloader_seed_args(args.collect()),
        Some("--help") | Some("-h") | None => {
            print_dataloader_help();
            std::process::exit(0);
        }
        Some(command) => Err(format!("unknown dataloader command `{command}`").into()),
    }
}

fn parse_dataloader_seed_args(args: Vec<String>) -> Result<Cli, Box<dyn std::error::Error>> {
    let mut args = args.into_iter();
    let mut output_dir = PathBuf::from("data/generated");
    let mut start_date = "2020-01-01".to_string();
    let mut end_date = "2020-01-31".to_string();
    let mut n_scenarios = 3usize;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--output" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --output".into());
                };
                output_dir = PathBuf::from(value);
            }
            "--start-date" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --start-date".into());
                };
                start_date = value;
            }
            "--end-date" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --end-date".into());
                };
                end_date = value;
            }
            "--scenarios" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --scenarios".into());
                };
                n_scenarios = value.parse()?;
            }
            "--help" | "-h" => {
                print_dataloader_seed_help();
                std::process::exit(0);
            }
            value => return Err(format!("unknown dataloader seed argument `{value}`").into()),
        }
    }

    Ok(Cli {
        command: Command::DataloaderSeed(DataloaderSeedCli {
            output_dir,
            start_date,
            end_date,
            n_scenarios,
        }),
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
    eprintln!("Usage:");
    eprintln!("  nrsm-cli <SCENARIO_PATH> [--output yaml|json] [--json] [--yaml] [--pretty]");
    eprintln!(
        "  nrsm-cli dataloader seed [--output DIR] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--scenarios N]"
    );
}

fn print_dataloader_help() {
    eprintln!("Usage: nrsm-cli dataloader <COMMAND>");
    eprintln!();
    eprintln!("Commands:");
    eprintln!("  seed    Generate seed config.yaml, module CSVs, and source staging tables");
}

fn print_dataloader_seed_help() {
    eprintln!(
        "Usage: nrsm-cli dataloader seed [--output DIR] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--scenarios N]"
    );
}
