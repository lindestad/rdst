import typer

app = typer.Typer(help="Nile digital twin dataloader")


@app.command()
def nodes(stub: bool = typer.Option(False, help="Produce stub data (fast)")) -> None:
    """Write nodes.geojson and node_config.yaml."""
    from dataloader import nodes as _nodes
    _nodes.build(stub=stub)


@app.command()
def forcings(stub: bool = False) -> None:
    """Fetch ERA5 forcings and write per-node timeseries Parquet."""
    from dataloader import forcings as _forcings
    _forcings.build(stub=stub)


@app.command()
def overlays(stub: bool = False) -> None:
    """Fetch Sentinel-2/CGLS NDVI and write overlays Parquet."""
    from dataloader import overlays as _overlays
    _overlays.build(stub=stub)


@app.command("csv-bundle")
def csv_bundle(
    stub: bool = typer.Option(False, help="Produce schema-correct synthetic CSVs"),
    profile: str = typer.Option(
        "core",
        help="Dataset profile to build: core, hydro, or full",
    ),
    start: str | None = typer.Option(None, help="Inclusive start date, YYYY-MM-DD"),
    end: str | None = typer.Option(None, help="Inclusive end date, YYYY-MM-DD"),
    overwrite: bool = typer.Option(False, help="Rewrite existing CSV outputs"),
) -> None:
    """Write a structured Copernicus/ERA5 CSV bundle under data/csv."""
    from dataloader import copernicus_csv as _csv
    _csv.build(stub=stub, profile=profile, start=start, end=end, overwrite=overwrite)


@app.command()
def tiles() -> None:
    """Render NDVI raster tile pyramid."""
    from dataloader import tiles as _tiles
    _tiles.build()


@app.command("all")
def all_(stub: bool = False) -> None:
    """Run nodes → forcings → overlays → tiles."""
    nodes(stub=stub)
    forcings(stub=stub)
    overlays(stub=stub)
    if not stub:
        tiles()


if __name__ == "__main__":
    app()
