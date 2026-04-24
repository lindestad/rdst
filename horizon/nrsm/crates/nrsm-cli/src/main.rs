use std::{fs, path::PathBuf};

use nrsm_sim_core::{Scenario, simulate};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (scenario_path, pretty) = parse_args()?;
    let scenario_contents = fs::read_to_string(&scenario_path)?;
    let scenario: Scenario = serde_json::from_str(&scenario_contents)?;
    let result = simulate(&scenario)?;

    if pretty {
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else {
        println!("{}", serde_json::to_string(&result)?);
    }

    Ok(())
}

fn parse_args() -> Result<(PathBuf, bool), Box<dyn std::error::Error>> {
    let args = std::env::args().skip(1);
    let mut scenario_path = None;
    let mut pretty = false;

    for arg in args {
        match arg.as_str() {
            "--pretty" => pretty = true,
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

    Ok((scenario_path, pretty))
}

fn print_help() {
    eprintln!("Usage: nrsm-cli <SCENARIO_PATH> [--pretty]");
}
