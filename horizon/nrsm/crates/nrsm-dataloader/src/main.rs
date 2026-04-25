use std::path::PathBuf;

use nrsm_dataloader::{SnapshotOptions, write_seed_snapshot};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = parse_args()?;

    match cli.command {
        Command::Seed(seed) => {
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
        }
    }

    Ok(())
}

#[derive(Debug)]
struct Cli {
    command: Command,
}

#[derive(Debug)]
enum Command {
    Seed(SeedCli),
}

#[derive(Debug)]
struct SeedCli {
    output_dir: PathBuf,
    start_date: String,
    end_date: String,
    n_scenarios: usize,
}

fn parse_args() -> Result<Cli, Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);

    match args.next().as_deref() {
        Some("seed") => parse_seed_args(args.collect()),
        Some("--help") | Some("-h") | None => {
            print_help();
            std::process::exit(0);
        }
        Some(command) => Err(format!("unknown dataloader command `{command}`").into()),
    }
}

fn parse_seed_args(args: Vec<String>) -> Result<Cli, Box<dyn std::error::Error>> {
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
                print_seed_help();
                std::process::exit(0);
            }
            value => return Err(format!("unknown seed argument `{value}`").into()),
        }
    }

    Ok(Cli {
        command: Command::Seed(SeedCli {
            output_dir,
            start_date,
            end_date,
            n_scenarios,
        }),
    })
}

fn print_help() {
    eprintln!("Usage: nrsm-dataloader <COMMAND>");
    eprintln!();
    eprintln!("Commands:");
    eprintln!("  seed    Generate config.yaml, module CSVs, and source staging tables");
}

fn print_seed_help() {
    eprintln!(
        "Usage: nrsm-dataloader seed [--output DIR] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--scenarios N]"
    );
}
