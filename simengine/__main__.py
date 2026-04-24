import typer

app = typer.Typer(help="Nile digital twin sim engine")


@app.command()
def run(
    scenario: str = typer.Option(..., help="Path to scenario JSON"),
    config: str = typer.Option("data/node_config.yaml", help="Node config YAML"),
    data: str = typer.Option("data/timeseries", help="Timeseries Parquet dir"),
    out: str = typer.Option(None, help="Output scenario JSON (default: overwrite input)"),
) -> None:
    """Run a scenario and write results back to the scenario JSON."""
    from simengine.engine import run_scenario_file
    run_scenario_file(scenario, config, data, out)


if __name__ == "__main__":
    app()
