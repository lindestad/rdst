use std::{fs, path::PathBuf};

use nrsm_dataloader::{
    AssembleOptions, SnapshotOptions, assemble_horizon_data_snapshot, write_seed_snapshot,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = parse_args()?;

    match cli.command {
        Command::Assemble(assemble) => {
            let outputs = assemble_horizon_data_snapshot(&AssembleOptions {
                input_dir: assemble.input_dir,
                output_dir: assemble.output_dir.clone(),
                start_date: assemble.start_date,
                end_date: assemble.end_date,
                node_ids: assemble.node_ids,
                inflow_scale: assemble.inflow_scale,
            })?;
            println!(
                "Wrote {} assembled dataloader files to {}",
                outputs.len(),
                assemble.output_dir.display()
            );
        }
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
    Assemble(AssembleCli),
    Seed(SeedCli),
}

#[derive(Debug)]
struct AssembleCli {
    input_dir: PathBuf,
    output_dir: PathBuf,
    start_date: String,
    end_date: String,
    node_ids: Option<Vec<String>>,
    inflow_scale: f64,
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
        Some("assemble") => parse_assemble_args(args.collect()),
        Some("seed") => parse_seed_args(args.collect()),
        Some("--help") | Some("-h") | None => {
            print_help();
            std::process::exit(0);
        }
        Some(command) => Err(format!("unknown dataloader command `{command}`").into()),
    }
}

fn parse_assemble_args(args: Vec<String>) -> Result<Cli, Box<dyn std::error::Error>> {
    let mut args = args.into_iter();
    let defaults = AssembleOptions::default();
    let mut input_dir = defaults.input_dir;
    let mut output_dir = None;
    let mut period_path = None;
    let mut start_date = None;
    let mut end_date = None;
    let mut inflow_scale = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--period" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --period".into());
                };
                period_path = Some(PathBuf::from(value));
            }
            "--input" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --input".into());
                };
                input_dir = PathBuf::from(value);
            }
            "--output" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --output".into());
                };
                output_dir = Some(PathBuf::from(value));
            }
            "--start-date" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --start-date".into());
                };
                start_date = Some(value);
            }
            "--end-date" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --end-date".into());
                };
                end_date = Some(value);
            }
            "--inflow-scale" => {
                let Some(value) = args.next() else {
                    return Err("missing value for --inflow-scale".into());
                };
                inflow_scale = Some(value.parse::<f64>()?);
            }
            "--help" | "-h" => {
                print_assemble_help();
                std::process::exit(0);
            }
            value => return Err(format!("unknown assemble argument `{value}`").into()),
        }
    }

    let period = period_path
        .as_ref()
        .map(|path| read_period_spec(path))
        .transpose()?;
    let start_date = start_date
        .or_else(|| period.as_ref().map(|period| period.start_date.clone()))
        .unwrap_or(defaults.start_date);
    let end_date = end_date
        .or_else(|| period.as_ref().map(|period| period.end_date.clone()))
        .unwrap_or(defaults.end_date);
    let node_ids = period.as_ref().and_then(|period| period.node_ids.clone());
    let inflow_scale = inflow_scale
        .or_else(|| period.as_ref().map(|period| period.inflow_scale))
        .unwrap_or(defaults.inflow_scale);
    if inflow_scale < 0.0 {
        return Err("inflow scale must be non-negative".into());
    }
    let output_dir = output_dir.unwrap_or_else(|| {
        period_path
            .as_ref()
            .and_then(|path| path.file_stem())
            .and_then(|stem| stem.to_str())
            .map(|stem| PathBuf::from("data").join("generated").join(stem))
            .unwrap_or(defaults.output_dir)
    });

    Ok(Cli {
        command: Command::Assemble(AssembleCli {
            input_dir,
            output_dir,
            start_date,
            end_date,
            node_ids,
            inflow_scale,
        }),
    })
}

#[derive(Debug)]
struct PeriodSpec {
    start_date: String,
    end_date: String,
    node_ids: Option<Vec<String>>,
    inflow_scale: f64,
}

fn read_period_spec(path: &PathBuf) -> Result<PeriodSpec, Box<dyn std::error::Error>> {
    let contents = fs::read_to_string(path)?;
    let value: serde_yaml::Value = serde_yaml::from_str(&contents)?;
    let settings = value
        .get("settings")
        .ok_or("period file must contain a `settings` mapping")?;
    let start_date = required_string_setting(settings, "start_date", path)?;
    let end_date = required_string_setting(settings, "end_date", path)?;
    let node_ids = optional_string_list_setting(settings, "node_ids", path)?;
    let inflow_scale = optional_f64_setting(settings, "inflow_scale", path)?.unwrap_or(1.0);
    if inflow_scale < 0.0 {
        return Err(format!(
            "period file `{}` setting `settings.inflow_scale` must be non-negative",
            path.display()
        )
        .into());
    }

    Ok(PeriodSpec {
        start_date,
        end_date,
        node_ids,
        inflow_scale,
    })
}

fn required_string_setting(
    settings: &serde_yaml::Value,
    field: &str,
    path: &PathBuf,
) -> Result<String, Box<dyn std::error::Error>> {
    let value = settings.get(field).ok_or_else(|| {
        format!(
            "period file `{}` must contain `settings.{field}`",
            path.display()
        )
    })?;
    if let Some(text) = value.as_str() {
        return Ok(text.to_string());
    }
    Err(format!(
        "period file `{}` setting `settings.{field}` must be a YYYY-MM-DD string",
        path.display()
    )
    .into())
}

fn optional_string_list_setting(
    settings: &serde_yaml::Value,
    field: &str,
    path: &PathBuf,
) -> Result<Option<Vec<String>>, Box<dyn std::error::Error>> {
    let Some(value) = settings.get(field) else {
        return Ok(None);
    };
    let Some(items) = value.as_sequence() else {
        return Err(format!(
            "period file `{}` setting `settings.{field}` must be a list of node ids",
            path.display()
        )
        .into());
    };

    let mut strings = Vec::with_capacity(items.len());
    for item in items {
        let Some(text) = item.as_str() else {
            return Err(format!(
                "period file `{}` setting `settings.{field}` must contain only strings",
                path.display()
            )
            .into());
        };
        strings.push(text.to_string());
    }
    Ok(Some(strings))
}

fn optional_f64_setting(
    settings: &serde_yaml::Value,
    field: &str,
    path: &PathBuf,
) -> Result<Option<f64>, Box<dyn std::error::Error>> {
    let Some(value) = settings.get(field) else {
        return Ok(None);
    };
    if let Some(number) = value.as_f64() {
        return Ok(Some(number));
    }
    Err(format!(
        "period file `{}` setting `settings.{field}` must be a number",
        path.display()
    )
    .into())
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
    eprintln!("  assemble    Generate config.yaml and module CSVs from horizon/data");
    eprintln!(
        "  seed        Generate deterministic seed config, module CSVs, and source staging tables"
    );
}

fn print_assemble_help() {
    eprintln!(
        "Usage: nrsm-dataloader assemble [--period FILE] [--input DIR] [--output DIR] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--inflow-scale N]"
    );
}

fn print_seed_help() {
    eprintln!(
        "Usage: nrsm-dataloader seed [--output DIR] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--scenarios N]"
    );
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::{Command, parse_assemble_args, read_period_spec};

    #[test]
    fn reads_period_from_yaml_settings() {
        let dir = std::env::temp_dir().join(format!(
            "nrsm-period-spec-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        ));
        fs::create_dir_all(&dir).expect("temp dir should be created");
        let path = dir.join("wet-season.yaml");
        fs::write(
            &path,
            "settings:\n  start_date: 1963-09-01\n  end_date: 1963-09-30\n  inflow_scale: 0.7\n  node_ids:\n    - tana\n    - gerd\nnodes: []\n",
        )
        .expect("period file should be written");

        let period = read_period_spec(&path).expect("period should parse");

        assert_eq!(period.start_date, "1963-09-01");
        assert_eq!(period.end_date, "1963-09-30");
        assert_eq!(
            period.node_ids,
            Some(vec!["tana".to_string(), "gerd".to_string()])
        );
        assert_eq!(period.inflow_scale, 0.7);

        fs::remove_dir_all(&dir).expect("temp dir should be removed");
    }

    #[test]
    fn assemble_period_defaults_output_to_period_stem() {
        let dir = std::env::temp_dir().join(format!(
            "nrsm-period-args-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("system time should be after epoch")
                .as_nanos()
        ));
        fs::create_dir_all(&dir).expect("temp dir should be created");
        let path = dir.join("1963-september-30d.yaml");
        fs::write(
            &path,
            "settings:\n  start_date: 1963-09-01\n  end_date: 1963-09-30\n",
        )
        .expect("period file should be written");

        let cli = parse_assemble_args(vec![
            "--period".to_string(),
            path.to_string_lossy().to_string(),
        ])
        .expect("args should parse");

        let Command::Assemble(assemble) = cli.command else {
            panic!("expected assemble command");
        };

        assert_eq!(assemble.start_date, "1963-09-01");
        assert_eq!(assemble.end_date, "1963-09-30");
        assert_eq!(assemble.node_ids, None);
        assert_eq!(assemble.inflow_scale, 1.0);
        assert_eq!(
            assemble.output_dir,
            std::path::PathBuf::from("data/generated/1963-september-30d")
        );

        fs::remove_dir_all(&dir).expect("temp dir should be removed");
    }

    #[test]
    fn assemble_args_accept_inflow_scale_override() {
        let cli = parse_assemble_args(vec![
            "--start-date".to_string(),
            "2005-01-01".to_string(),
            "--end-date".to_string(),
            "2005-01-31".to_string(),
            "--inflow-scale".to_string(),
            "0.4".to_string(),
        ])
        .expect("args should parse");

        let Command::Assemble(assemble) = cli.command else {
            panic!("expected assemble command");
        };

        assert_eq!(assemble.inflow_scale, 0.4);
    }
}
